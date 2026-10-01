"""Writer-isolation probe: refuse a comparison whose writer reads more than the skill text it is given.

A writer CLI can load project instruction files, user settings and memory on its own, and any of that text
would reach the model beside the skill under test. The probe sends one fixed line to the configured probe
command and reads the token counts the CLI reports for it. A prompt that is larger than the limit means
something besides the fixed line was loaded, so the run refuses before it spends a model call on it."""
from __future__ import annotations

import tempfile

from .adapters import canonical_bytes, digest, run_captured
from .contracts import strict_json

PROBE_PROMPT='Reply with the single word ok.'
DEFAULT_TIMEOUT_SECONDS=120
# Cached input counts too: an instruction file usually reaches the model as cache_creation or cache_read tokens.
USAGE_FIELDS=('input_tokens','cache_creation_input_tokens','cache_read_input_tokens')
# These three templates are quoted verbatim in CONTRACT.md, and the contract tests pin them.
OVER_LIMIT='isolation probe: writer prompt is {tokens} tokens, over the limit of {limit}'
FAILED='isolation probe failed: {reason}'
UNPARSABLE='isolation probe output cannot be parsed: {reason}'


def run_probe(settings,*,timeout_seconds=DEFAULT_TIMEOUT_SECONDS):
    """Run the configured probe once and return its provenance record, or None when the config declares no probe.

    The record is {command_sha256, max_prompt_tokens, prompt_tokens}. A probe that cannot start, times out, exits
    nonzero, reports an error, prints something unreadable or reports more than max_prompt_tokens raises ValueError
    with one of the templates above. The probe runs from a scratch folder, like each writer call."""
    if settings is None:
        return None
    command=settings['command']
    limit=settings['max_prompt_tokens']
    with tempfile.TemporaryDirectory(prefix='wq-probe-',ignore_cleanup_errors=True) as scratch:
        done=run_captured(command,stdin_text=PROBE_PROMPT,cwd=scratch,timeout=timeout_seconds)
    if done['launch_error'] is not None:
        raise ValueError(FAILED.format(reason=f"could not start: {done['launch_error']}"))
    if done['timed_out']:
        raise ValueError(FAILED.format(reason=f'timed out after {timeout_seconds:g} seconds'))
    if done['returncode']!=0:
        raise ValueError(FAILED.format(reason=f"exit code {done['returncode']}"))
    tokens=_prompt_tokens(done['stdout'])
    if tokens>limit:
        raise ValueError(OVER_LIMIT.format(tokens=tokens,limit=limit))
    return {'command_sha256':digest(canonical_bytes(command)),'max_prompt_tokens':limit,'prompt_tokens':tokens}


def _unparsable(reason):
    return ValueError(UNPARSABLE.format(reason=reason))


def _prompt_tokens(text):
    """Sum the three usage counts of the probe's JSON output (one result object, or a list holding one result event)."""
    try:
        value=strict_json(text.encode('utf-8'))
    except ValueError as exc:
        raise _unparsable(str(exc)) from None
    if isinstance(value,list):
        events=[event for event in value if isinstance(event,dict) and event.get('type')=='result']
        if len(events)!=1:
            raise _unparsable('the output list needs exactly one result event')
        value=events[0]
    if not isinstance(value,dict):
        raise _unparsable('the output is not a JSON object')
    if value.get('is_error') is True:
        raise ValueError(FAILED.format(reason='the probe reported an error'))
    usage=value.get('usage')
    if not isinstance(usage,dict):
        raise _unparsable('the output has no usage object')
    total=0
    for name in USAGE_FIELDS:
        # Only input_tokens must be present; a cache count that is absent is zero, but one that is present must be a count.
        if name not in usage and name!='input_tokens':
            continue
        count=usage.get(name)
        if isinstance(count,bool) or not isinstance(count,int) or count<0:
            raise _unparsable(f'usage.{name} is not a nonnegative integer')
        total+=count
    return total
