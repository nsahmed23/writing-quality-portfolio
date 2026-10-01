"""Private outputs: where a run made from owner text may be written.

A suite with any owner_session case holds the owner's own writing, so every command that writes from it refuses
an output path outside the folder named by WQ_EVAL_PRIVATE_ROOT. Paths are compared after os.path.realpath, so a
symlink, a junction or a .. cannot lead out of the root. The check runs right after the suite loads, before any
output exists. Its messages name the variable and never a path, so owner text and locations cannot reach an
error line. A suite with no owner_session case is not checked at all."""
from __future__ import annotations

import os

PRIVATE_ROOT_ENV='WQ_EVAL_PRIVATE_ROOT'


def has_owner_session(suite):
    """True when any case of a loaded suite has provenance kind owner_session."""
    return any(case['provenance']['kind']=='owner_session' for case in suite['cases'])


def _inside(root,path):
    """True when path is the root or lies under it; both are resolved real paths."""
    root=os.path.normcase(root); path=os.path.normcase(path)
    try: return os.path.commonpath([root,path])==root
    except ValueError: return False  # paths on different drives share nothing, so the path is outside


def require_private_output(suite,out):
    """Refuse an output path outside WQ_EVAL_PRIVATE_ROOT when the suite has owner_session cases.

    The variable is read at call time. An unset or blank variable refuses, and so does a root that is not an
    existing folder (a typo must not create a new private folder). Nothing is created here."""
    if not has_owner_session(suite): return
    raw=os.environ.get(PRIVATE_ROOT_ENV,'')
    if not raw.strip():
        raise ValueError(f'suite has owner_session cases; set {PRIVATE_ROOT_ENV} to a private folder and write the run inside it')
    root=os.path.realpath(raw)
    if not os.path.isdir(root): raise ValueError(f'{PRIVATE_ROOT_ENV} must name an existing folder')
    if not _inside(root,os.path.realpath(out)):
        raise ValueError(f'suite has owner_session cases; the output path must be inside {PRIVATE_ROOT_ENV}')
