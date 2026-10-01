"""Tests for the owner-session harvester.

Every transcript line below is synthetic text invented for the test. No owner text belongs in this file."""
import contextlib
import io
import itertools
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evaluation.benchmark_v2.automated import contracts
from evaluation.benchmark_v2.automated.tools import harvest

PRIVATE_ENV = 'WQ_EVAL_PRIVATE_ROOT'
SOURCE = ('Hi Dana, I wanted to follow up on the invoice we discussed last week. '
          'Could you confirm the payment date by Friday? Thanks, Sam')
ASK = 'Tighten this email.'


def user(text, uuid='u1', session='s1', **extra):
    event = {'type': 'user', 'uuid': uuid, 'sessionId': session,
             'message': {'role': 'user', 'content': text}}
    event.update(extra)
    return event


def assistant(text, uuid='a1', session='s1', **extra):
    event = {'type': 'assistant', 'uuid': uuid, 'sessionId': session,
             'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': text}]}}
    event.update(extra)
    return event


def tool_result(uuid='t1', session='s1'):
    return {'type': 'user', 'uuid': uuid, 'sessionId': session,
            'message': {'role': 'user', 'content': [
                {'type': 'tool_result', 'tool_use_id': 'x', 'content': 'Rewrite this: ' + SOURCE}]}}


class Workspace(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        base = Path(self._tmp.name)
        self.projects = base / 'projects'
        self.private = base / 'private'
        self.projects.mkdir()
        self.private.mkdir()
        patcher = mock.patch.dict(os.environ, {PRIVATE_ENV: str(self.private)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self._runs = itertools.count(1)
        self.out = self.fresh_out()

    def fresh_out(self):
        return self.private / 'harvest' / f'run-{next(self._runs)}'

    def transcript(self, project, name, events, subdir=None):
        folder = self.projects / project
        if subdir:
            folder = folder / subdir
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f'{name}.jsonl'
        with open(path, 'w', encoding='utf-8', newline='\n') as fh:
            for event in events:
                fh.write((event if isinstance(event, str) else json.dumps(event)) + '\n')
        return path

    def run_harvest(self, *extra, out=None):
        argv = ['--projects-root', str(self.projects), '--out', str(out or self.out), *extra]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = harvest.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def load(self, out=None):
        out = out or self.out

        def read(name):
            return json.loads((out / name).read_text(encoding='utf-8'))
        return read('candidates.json'), read('sidecar.json'), read('exclusions.json')

    def harvest_ok(self, events, project='proj-a', out=None):
        self.transcript(project, 'session-1', events)
        out = out or self.out
        code, _, stderr = self.run_harvest('--allow-all', out=out)
        self.assertEqual(code, 0, stderr)
        return self.load(out)

    def one_case(self, events):
        candidates, sidecar, exclusions = self.harvest_ok(events)
        self.assertEqual(len(candidates['cases']), 1)
        case = candidates['cases'][0]
        return case, sidecar['cases'][case['id']], exclusions


class DenyByDefault(Workspace):
    def test_no_allow_flag_exits_2_and_writes_nothing(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        code, _, stderr = self.run_harvest()
        self.assertEqual(code, 2)
        self.assertIn('--allow', stderr)
        self.assertFalse(self.out.exists())

    def test_allow_names_one_project(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE, uuid='ua')])
        self.transcript('proj-b', 'two', [user(ASK + '\n' + SOURCE + ' B', uuid='ub', session='s2')])
        self.assertEqual(self.run_harvest('--allow', 'proj-b')[0], 0)
        cases = self.load()[0]['cases']
        self.assertEqual([c['provenance']['source'] for c in cases], ['proj-b'])

    def test_allow_may_repeat(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE, uuid='ua')])
        self.transcript('proj-b', 'two', [user(ASK + '\n' + SOURCE + ' B', uuid='ub', session='s2')])
        self.transcript('proj-c', 'three', [user(ASK + '\n' + SOURCE + ' C', uuid='uc', session='s3')])
        self.assertEqual(self.run_harvest('--allow', 'proj-a', '--allow', 'proj-c')[0], 0)
        cases = self.load()[0]['cases']
        self.assertEqual([c['provenance']['source'] for c in cases], ['proj-a', 'proj-c'])

    def test_unknown_allow_name_exits_2(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        code, _, _ = self.run_harvest('--allow', 'no-such-project')
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())

    def test_allow_and_allow_all_together_exit_2(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        code, _, _ = self.run_harvest('--allow', 'proj-a', '--allow-all')
        self.assertEqual(code, 2)
        self.assertFalse(self.out.exists())

    def test_missing_projects_root_exits_2(self):
        argv = ['--projects-root', str(self.projects / 'absent'), '--out', str(self.out), '--allow-all']
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(harvest.main(argv), 2)


class OutputGuards(Workspace):
    def test_out_outside_private_root_exits_2(self):
        elsewhere = Path(self._tmp.name) / 'elsewhere'
        elsewhere.mkdir()
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        code, _, stderr = self.run_harvest('--allow-all', out=elsewhere / 'v1')
        self.assertEqual(code, 2)
        self.assertIn(PRIVATE_ENV, stderr)
        self.assertFalse((elsewhere / 'v1').exists())

    def test_dotdot_cannot_lead_out_of_the_private_root(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        (self.private / 'harvest').mkdir()
        sneaky = self.private / 'harvest' / '..' / '..' / 'escaped'
        code, _, _ = self.run_harvest('--allow-all', out=sneaky)
        self.assertEqual(code, 2)
        self.assertFalse((Path(self._tmp.name) / 'escaped').exists())

    def test_unset_private_root_exits_2(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        with mock.patch.dict(os.environ):
            os.environ.pop(PRIVATE_ENV, None)
            code, _, stderr = self.run_harvest('--allow-all')
        self.assertEqual(code, 2)
        self.assertIn(PRIVATE_ENV, stderr)
        self.assertFalse(self.out.exists())

    def test_refuses_to_overwrite_existing_output(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        self.assertEqual(self.run_harvest('--allow-all')[0], 0)
        before = {n: (self.out / n).read_bytes() for n in ('candidates.json', 'sidecar.json', 'exclusions.json')}
        code, _, stderr = self.run_harvest('--allow-all')
        self.assertEqual(code, 2)
        self.assertIn('overwrite', stderr)
        after = {n: (self.out / n).read_bytes() for n in before}
        self.assertEqual(before, after)

    def test_writes_exactly_three_files(self):
        self.harvest_ok([user(ASK + '\n' + SOURCE)])
        self.assertEqual(sorted(p.name for p in self.out.iterdir()),
                         ['candidates.json', 'exclusions.json', 'sidecar.json'])


class SkipRules(Workspace):
    def assert_skipped(self, event, reason):
        out = self.fresh_out()
        candidates, _, report = self.harvest_ok([event], out=out)
        self.assertEqual(candidates['cases'], [], reason)
        self.assertEqual(report['skipped_turns'], {reason: 1})
        self.assertEqual(report['owner_turns'], 0)

    def test_turns_that_are_not_the_owners_typing(self):
        base = ASK + '\n' + SOURCE
        cases = [
            ('tool_result', tool_result()),
            ('meta', user(base, isMeta=True)),
            ('sidechain', user(base, isSidechain=True)),
            ('compact_summary', user('This session is being continued from a previous conversation that ran out of '
                                     'context. ' + base)),
            ('compact_summary', user(base, isCompactSummary=True)),
            ('command_wrapper', user('<command-name>/rewrite</command-name>\n' + base)),
            ('command_wrapper', user('<local-command-stdout>' + base + '</local-command-stdout>')),
            ('system_reminder_only', user('<system-reminder>\n' + base + '\n</system-reminder>')),
            ('machine_origin', user(base, origin={'kind': 'task-notification'})),
            ('programmatic', user(base, promptSource='sdk')),
            ('programmatic', user(base, promptSource='system')),
            ('machine_text', user('Another Claude session sent a message.\n' + base)),
            ('machine_text', user('<teammate-message from="x">' + base + '</teammate-message>')),
            ('machine_text', user('<task-notification>' + base + '</task-notification>')),
            ('machine_text', user('[Request interrupted by user]')),
            ('empty', user('   \n')),
            ('empty', {'type': 'user', 'uuid': 'u9', 'sessionId': 's1', 'message': {
                'role': 'user', 'content': [{'type': 'image', 'source': {}}]}}),
        ]
        for reason, event in cases:
            with self.subTest(reason=reason, text=str(event['message']['content'])[:20]):
                self.assert_skipped(event, reason)

    def test_human_origin_is_still_an_owner_turn(self):
        case, _, _ = self.one_case([user(ASK + '\n' + SOURCE, origin={'kind': 'human'}, promptSource='user')])
        self.assertEqual(case['context'], SOURCE)

    def test_system_reminder_blocks_are_stripped_from_owner_text(self):
        text = ('<system-reminder>\nREMINDER-BODY\n</system-reminder>\n' + ASK + '\n' + SOURCE
                + '\n<system-reminder>REMINDER-TAIL</system-reminder>')
        candidates, _, _ = self.harvest_ok([user(text)])
        case = candidates['cases'][0]
        self.assertEqual(case['prompt'], ASK)
        self.assertEqual(case['context'], SOURCE)
        self.assertNotIn('REMINDER', json.dumps(candidates))

    def test_turn_with_no_instruction_verb_is_excluded(self):
        candidates, _, report = self.harvest_ok([user('Here is the invoice thread.\n' + SOURCE)])
        self.assertEqual(candidates['cases'], [])
        self.assertEqual(report['exclusions'], {'no_instruction': 1})
        self.assertEqual(report['owner_turns'], 1)

    def test_verb_inside_the_pasted_source_is_not_an_instruction(self):
        text = 'See below.\n<pasted_content>Please tighten the schedule.</pasted_content>'
        _, _, report = self.harvest_ok([user(text)])
        self.assertEqual(report['exclusions'], {'no_instruction': 1})


class SourceKinds(Workspace):
    def test_pasted_block(self):
        text = 'Please tighten this email.\n<pasted_content name="draft.txt">\n' + SOURCE + '\n</pasted_content>'
        case, hint, _ = self.one_case([assistant('PRIOR-ASSISTANT-TEXT'), user(text)])
        self.assertEqual(case['prompt'], 'Please tighten this email.')
        self.assertEqual(case['context'], SOURCE)
        self.assertNotIn('PRIOR', json.dumps(case))
        self.assertEqual((hint['source_kind'], hint['has_pasted_content']), ('pasted', True))

    def test_pasted_block_may_be_short(self):
        case, hint, _ = self.one_case([user('Reword this.\n<pasted_content>Ok thanks</pasted_content>')])
        self.assertEqual(case['context'], 'Ok thanks')
        self.assertEqual(hint['source_kind'], 'pasted')

    def test_instruction_only_around_a_pasted_block_is_not_enough(self):
        _, _, report = self.harvest_ok([user('<pasted_content>' + SOURCE + '</pasted_content>')])
        self.assertEqual(report['exclusions'], {'no_instruction': 1})

    def test_fenced_block(self):
        case, hint, _ = self.one_case([user('Rewrite this announcement:\n```\n' + SOURCE + '\n```')])
        self.assertEqual(case['prompt'], 'Rewrite this announcement:')
        self.assertEqual(case['context'], SOURCE)
        self.assertEqual((hint['source_kind'], hint['has_pasted_content']), ('fenced', False))
        self.assertEqual(case['lane'], 'communication')

    def test_code_fence_is_not_prose(self):
        candidates, _, report = self.harvest_ok([user('Write this up properly.\n```python\nprint("hi")\n```')])
        self.assertEqual(candidates['cases'], [])
        self.assertEqual(report['exclusions'], {'code_source': 1})

    def test_inline_text_after_the_instruction_line(self):
        case, hint, _ = self.one_case([user(ASK + '\n\n' + SOURCE)])
        self.assertEqual(case['prompt'], ASK)
        self.assertEqual(case['context'], SOURCE)
        self.assertEqual((hint['source_kind'], hint['has_pasted_content']), ('inline', False))

    def test_inline_text_after_a_colon_on_one_line(self):
        case, hint, _ = self.one_case([user('Rewrite this email: ' + SOURCE)])
        self.assertEqual(case['prompt'], 'Rewrite this email:')
        self.assertEqual(case['context'], SOURCE)
        self.assertEqual(hint['source_kind'], 'inline')

    def test_inline_text_needs_80_characters(self):
        for size, expected in ((79, 'no_source'), (80, None)):
            with self.subTest(size=size):
                out = self.fresh_out()
                candidates, _, report = self.harvest_ok([user(ASK + '\n' + 'a' * size)], out=out)
                if expected:
                    self.assertEqual(candidates['cases'], [])
                    self.assertEqual(report['exclusions'], {expected: 1})
                else:
                    self.assertEqual(len(candidates['cases']), 1)

    def test_previous_assistant_text_when_the_turn_names_no_source(self):
        events = [user('Draft a reply to Dana.', uuid='u0'), assistant(SOURCE), user('Make it shorter.', uuid='u1')]
        candidates, sidecar, report = self.harvest_ok(events)
        self.assertEqual(len(candidates['cases']), 1)
        case = candidates['cases'][0]
        self.assertEqual((case['prompt'], case['context'], case['a'], case['b']),
                         ('Make it shorter.', SOURCE, SOURCE, SOURCE))
        self.assertEqual(sidecar['cases'][case['id']]['source_kind'], 'previous_assistant')
        self.assertFalse(sidecar['cases'][case['id']]['has_pasted_content'])
        self.assertEqual(report['exclusions'], {'no_source': 1})

    def test_no_previous_assistant_means_no_source(self):
        _, _, report = self.harvest_ok([user('Tighten that.')])
        self.assertEqual(report['exclusions'], {'no_source': 1})

    def test_previous_assistant_text_serves_one_turn_only(self):
        events = [assistant(SOURCE), user('Tighten that.', uuid='u1'), user('Shorten it more.', uuid='u2')]
        candidates, _, report = self.harvest_ok(events)
        self.assertEqual(len(candidates['cases']), 1)
        self.assertEqual(report['exclusions'], {'no_source': 1})

    def test_previous_assistant_needs_a_pointer_word(self):
        _, _, report = self.harvest_ok([assistant(SOURCE), user('Write the migration script for the billing table.')])
        self.assertEqual(report['exclusions'], {'no_source': 1})

    def test_previous_assistant_is_the_message_right_before_the_turn(self):
        events = [assistant('OLDER-TEXT', uuid='a0'), tool_result(), assistant(SOURCE, uuid='a1'),
                  user('Tighten that.', uuid='u1')]
        case, _, _ = self.one_case(events)
        self.assertEqual(case['context'], SOURCE)

    def test_text_blocks_of_a_list_turn_are_joined(self):
        content = [{'type': 'text', 'text': ASK}, {'type': 'image', 'source': {}}, {'type': 'text', 'text': SOURCE}]
        event = {'type': 'user', 'uuid': 'u1', 'sessionId': 's1', 'message': {'role': 'user', 'content': content}}
        case, _, _ = self.one_case([event])
        self.assertEqual((case['prompt'], case['context']), (ASK, SOURCE))


class NoLeak(Workspace):
    def test_later_turns_never_enter_prompt_or_context(self):
        later_assistant, later_owner = 'LATER-ASSISTANT-TEXT', 'LATER-OWNER-TEXT'
        events = [assistant(SOURCE, uuid='a1'), user('Tighten that.', uuid='u1'),
                  assistant(later_assistant, uuid='a2'), user(later_owner, uuid='u2')]
        candidates, sidecar, _ = self.harvest_ok(events)
        case = candidates['cases'][0]
        for field in ('prompt', 'context', 'a', 'b'):
            self.assertNotIn('LATER', case[field])
        self.assertEqual(case['context'], SOURCE)
        self.assertNotIn('LATER', json.dumps(candidates))
        self.assertEqual(sidecar['cases'][case['id']]['correction'], later_owner)
        self.assertNotIn(later_assistant, json.dumps(sidecar))

    def test_later_turns_do_not_enter_an_inline_case_either(self):
        events = [user(ASK + '\n' + SOURCE, uuid='u1'), assistant('LATER-ASSISTANT-TEXT'), user('LATER-OWNER-TEXT', uuid='u2')]
        candidates, _, _ = self.harvest_ok(events)
        self.assertNotIn('LATER', json.dumps(candidates))


class Corrections(Workspace):
    CASE_TURN = ASK + '\n' + SOURCE

    def entry(self, events):
        candidates, sidecar, _ = self.harvest_ok(events)
        case = candidates['cases'][0]
        self.assertNotIn('correction', case)
        return sidecar['cases'][case['id']]

    def test_next_owner_turn_after_the_response_is_the_correction(self):
        events = [user(self.CASE_TURN, uuid='u1'), assistant('Here is a tighter version.'),
                  user('Too formal, use first names.', uuid='u2')]
        entry = self.entry(events)
        self.assertEqual(entry['correction'], 'Too formal, use first names.')
        self.assertFalse(entry['correction_truncated'])

    def test_correction_never_enters_the_case(self):
        events = [user(self.CASE_TURN, uuid='u1'), assistant('Here is a tighter version.'),
                  user('Too formal, use first names.', uuid='u2')]
        candidates, _, _ = self.harvest_ok(events)
        self.assertNotIn('Too formal', json.dumps(candidates))
        self.assertNotIn('tighter version', json.dumps(candidates))

    def test_tool_results_and_machine_turns_are_not_the_correction(self):
        events = [user(self.CASE_TURN, uuid='u1'), assistant('Here is a tighter version.'), tool_result(),
                  user('Another Claude session sent a note.', uuid='m1'), user('Use first names.', uuid='u2')]
        self.assertEqual(self.entry(events)['correction'], 'Use first names.')

    def test_system_reminders_are_stripped_from_the_correction(self):
        events = [user(self.CASE_TURN, uuid='u1'), assistant('Done.'),
                  user('<system-reminder>REMINDER-BODY</system-reminder>Use first names.', uuid='u2')]
        entry = self.entry(events)
        self.assertEqual(entry['correction'], 'Use first names.')

    def test_correction_is_capped_at_2500_characters(self):
        for size, truncated in ((3000, True), (2501, True), (2500, False)):
            with self.subTest(size=size):
                events = [user(self.CASE_TURN, uuid='u1'), assistant('Done.'), user('y' * size, uuid='u2')]
                out = self.fresh_out()
                candidates, sidecar, _ = self.harvest_ok(events, out=out)
                entry = sidecar['cases'][candidates['cases'][0]['id']]
                self.assertEqual(len(entry['correction']), 2500 if truncated else size)
                self.assertEqual(entry['correction_truncated'], truncated)

    def test_no_correction_without_an_assistant_response(self):
        events = [user(self.CASE_TURN, uuid='u1'), user('Use first names.', uuid='u2')]
        self.assertIsNone(self.entry(events)['correction'])

    def test_last_case_of_a_session_has_no_correction(self):
        entry = self.entry([user(self.CASE_TURN, uuid='u1'), assistant('Done.')])
        self.assertIsNone(entry['correction'])
        self.assertFalse(entry['correction_truncated'])

    def test_correction_does_not_cross_sessions(self):
        self.transcript('proj-a', 'one', [user(self.CASE_TURN, uuid='u1'), assistant('Done.')])
        self.transcript('proj-a', 'two', [user('Use first names.', uuid='u2', session='s2')])
        self.assertEqual(self.run_harvest('--allow-all')[0], 0)
        candidates, sidecar, _ = self.load()
        self.assertIsNone(sidecar['cases'][candidates['cases'][0]['id']]['correction'])


class Cap(Workspace):
    def test_context_over_2500_characters_is_excluded(self):
        for size, kept in ((2500, True), (2501, False)):
            with self.subTest(size=size):
                text = 'Tighten this.\n<pasted_content>' + 'a' * size + '</pasted_content>'
                candidates, _, report = self.harvest_ok([user(text)], out=self.fresh_out())
                self.assertEqual(len(candidates['cases']), 1 if kept else 0)
                self.assertEqual(report['exclusions'], {} if kept else {'over_cap': 1})

    def test_previous_assistant_text_over_the_cap_is_excluded(self):
        _, _, report = self.harvest_ok([assistant('b' * 2501), user('Tighten that.')])
        self.assertEqual(report['exclusions'], {'over_cap': 1})


class CaseShape(Workspace):
    def test_case_matches_the_ruled_shape(self):
        candidates, sidecar, _ = self.harvest_ok([user('Reply to this email, keep it friendly.\n' + SOURCE)],
                                                  project='proj-a')
        self.assertEqual(candidates['schema_version'], 1)
        case = candidates['cases'][0]
        self.assertEqual(set(case), {'id', 'document_id', 'lane', 'prompt', 'context', 'a', 'b', 'expected',
                                     'checks', 'provenance'})
        self.assertEqual(case['lane'], 'communication')
        self.assertEqual(case['prompt'], 'Reply to this email, keep it friendly.')
        self.assertEqual((case['context'], case['a'], case['b']), (SOURCE, SOURCE, SOURCE))
        self.assertIsNone(case['expected'])
        self.assertEqual(case['checks'], {})
        self.assertEqual(case['provenance']['kind'], 'owner_session')
        self.assertEqual(case['provenance']['source'], 'proj-a')
        self.assertTrue(case['provenance']['license'].strip())
        self.assertNotIn('split', case)
        self.assertEqual(set(sidecar['cases'][case['id']]),
                         {'correction', 'correction_truncated', 'source_kind', 'has_pasted_content'})

    def test_lane_is_editing_unless_the_request_is_a_message(self):
        for text, lane in (('Tighten this paragraph.', 'editing'), ('Draft an announcement from this:', 'communication'),
                           ('Respond to this.', 'communication'), ('Proofread this note.', 'editing')):
            with self.subTest(text=text):
                candidates, _, _ = self.harvest_ok([user(text + '\n' + SOURCE)], out=self.fresh_out())
                self.assertEqual(candidates['cases'][0]['lane'], lane)

    def test_ids_hash_session_and_turn_and_are_stable(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE, uuid='u1', session='sess-one'),
                                          user('Shorten this.\n' + SOURCE, uuid='u2', session='sess-one')])
        self.transcript('proj-a', 'two', [user(ASK + '\n' + SOURCE + ' B', uuid='u3', session='sess-two')])
        self.assertEqual(self.run_harvest('--allow-all')[0], 0)
        cases = self.load()[0]['cases']
        self.assertEqual(len(cases), 3)
        self.assertEqual(len({c['id'] for c in cases}), 3)
        self.assertEqual(cases[0]['document_id'], cases[1]['document_id'])
        self.assertNotEqual(cases[0]['document_id'], cases[2]['document_id'])
        for case in cases:
            for raw in ('sess-one', 'sess-two', 'u1', 'u2', 'u3'):
                self.assertNotIn(raw, case['id'] + case['document_id'])
        second = self.fresh_out()
        self.assertEqual(self.run_harvest('--allow-all', out=second)[0], 0)
        for name in ('candidates.json', 'sidecar.json', 'exclusions.json'):
            self.assertEqual((self.out / name).read_bytes(), (second / name).read_bytes())

    def test_identical_pair_from_another_session_is_excluded(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE, uuid='u1', session='s1')])
        self.transcript('proj-a', 'two', [user(ASK + '\n' + SOURCE, uuid='u2', session='s2')])
        self.assertEqual(self.run_harvest('--allow-all')[0], 0)
        candidates, _, report = self.load()
        self.assertEqual(len(candidates['cases']), 1)
        self.assertEqual(report['exclusions'], {'duplicate_pair': 1})

    def test_cases_pass_the_suite_contract_once_a_split_is_assigned(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE, uuid='u1', session='s1'),
                                          assistant(SOURCE + ' Again.'), user('Make it shorter.', uuid='u2')])
        self.transcript('proj-b', 'two', [user('Rewrite this:\n```\n' + SOURCE + ' B\n```', uuid='u3', session='s2')])
        self.assertEqual(self.run_harvest('--allow-all')[0], 0)
        candidates = self.load()[0]
        self.assertEqual(len(candidates['cases']), 3)
        suite = {'schema_version': 1, 'name': 'harvest-check',
                 'cases': [dict(case, split='development') for case in candidates['cases']]}
        contracts.validate_suite(suite)
        # split is absent on purpose; a later task assigns it, so the raw candidates are not yet a valid suite
        with self.assertRaises(ValueError):
            contracts.validate_suite({'schema_version': 1, 'name': 'harvest-check', 'cases': candidates['cases']})


class Walking(Workspace):
    def test_only_files_directly_inside_a_project_folder_are_read(self):
        self.transcript('proj-a', 'main', [user(ASK + '\n' + SOURCE, uuid='u1')])
        self.transcript('proj-a', 'sub', [user(ASK + '\n' + SOURCE + ' sub', uuid='u2')], subdir='subagents')
        self.transcript('proj-a', 'deep', [user(ASK + '\n' + SOURCE + ' deep', uuid='u3')], subdir='sess-1/subagents')
        (self.projects / 'proj-a' / 'notes.txt').write_text(ASK + '\n' + SOURCE, encoding='utf-8')
        (self.projects / 'stray.jsonl').write_text(json.dumps(user(ASK + '\n' + SOURCE + ' stray')) + '\n',
                                                    encoding='utf-8')
        self.assertEqual(self.run_harvest('--allow-all')[0], 0)
        candidates, _, report = self.load()
        self.assertEqual(len(candidates['cases']), 1)
        self.assertEqual(report['scanned']['files'], 1)
        self.assertEqual(report['scanned']['projects'], 1)

    def test_blank_and_unparsable_lines_are_skipped(self):
        events = ['', '{not json', json.dumps([1, 2]), user(ASK + '\n' + SOURCE)]
        candidates, _, report = self.harvest_ok(events)
        self.assertEqual(len(candidates['cases']), 1)
        self.assertEqual(report['scanned']['unparsable_lines'], 2)

    def test_files_are_streamed_line_by_line(self):
        self.transcript('proj-a', 'one', [user(ASK + '\n' + SOURCE)])
        with mock.patch.object(Path, 'read_text', side_effect=AssertionError('whole-file read')), \
                mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('whole-file read')):
            self.assertEqual(self.run_harvest('--allow-all')[0], 0)

    def test_lone_surrogates_do_not_break_the_output(self):
        event = user(ASK + '\n' + SOURCE + ' \ud83d')
        candidates, _, _ = self.harvest_ok([json.dumps(event)])
        contracts.strict_json(json.dumps(candidates).encode('utf-8'))
        self.assertEqual(len(candidates['cases']), 1)


class Aggregates(Workspace):
    def test_exclusions_file_and_stdout_hold_counts_only(self):
        mark = 'PLANTED-MARKER-7QX'
        self.transcript('proj-a', 'one', [
            user(ASK + '\n' + SOURCE + ' ' + mark, uuid='u1'),
            user('No instruction here ' + mark, uuid='u2'),
            user('Rewrite this.\n<pasted_content>' + 'z' * 3000 + mark + '</pasted_content>', uuid='u3')])
        code, stdout, stderr = self.run_harvest('--allow-all')
        self.assertEqual(code, 0, stderr)
        exclusions_text = (self.out / 'exclusions.json').read_text(encoding='utf-8')
        for blob in (stdout, stderr, exclusions_text):
            self.assertNotIn(mark, blob)
            self.assertNotIn('Dana', blob)
        report = json.loads(exclusions_text)
        self.assertEqual(report['owner_turns'], 3)
        self.assertEqual(report['exclusions'], {'no_instruction': 1, 'over_cap': 1})
        self.assertEqual(report['over_cap_length_buckets'], {'2501-5000': 1})
        cands = report['candidates']
        self.assertEqual(cands['total'], 1)
        self.assertEqual(cands['by_lane'], {'communication': 1})
        self.assertEqual(cands['by_source_kind'], {'inline': 1})
        self.assertEqual(cands['by_verb'], {'tighten': 1})
        self.assertEqual(cands['length_buckets'], {'0-299': 1})
        self.assertEqual(cands['projects'], 1)
        self.assertEqual(report['scanned']['projects'], 1)
        printed = json.loads(stdout)
        self.assertEqual(printed['candidates']['total'], 1)
        self.assertIn('elapsed_seconds', printed)

    def test_length_bucket_edges(self):
        for size, bucket in ((0, '0-299'), (299, '0-299'), (300, '300-999'), (999, '300-999'),
                             (1000, '1000-1999'), (1999, '1000-1999'), (2000, '2000-2500'), (2500, '2000-2500')):
            with self.subTest(size=size):
                self.assertEqual(harvest.length_bucket(size), bucket)


if __name__ == '__main__':
    unittest.main()
