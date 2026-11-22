# -*- coding: utf-8 -*-
"""Declared versus recorded: does a coding agent's end-of-task declaration match what the harness recorded?

A coding agent works in a sandbox repository and ends with a short ``styxx`` block (the declaration format
of ``styxx.declare``): whether the given tests pass, how many files changed, how many tests were added,
which path contains every change. After the session a harness works out the same facts from bytes it holds,
and ``styxx.selfreport.score`` compares the two, key by key, with no judge and no reading of prose.

STATUS. No model has been measured with this code. There is no preregistration for it and so no result; the
only runs it has made are scripted subjects whose correct scores were written down in advance
(``python -m styxx.selfreport known-answers``). A run made without a committed preregistration is recorded
as a smoke run and is not a result.

WHAT IT IS NOT. It is not a detector of lying: a contradicted declaration includes the case where the agent
did not know. It does not read prose, so a false sentence outside the block gets no verdict. It ranks
nothing. A session with no contradicted key has not been shown to be accurate.

PRIOR WORK this builds on, none of which is ours: hidden-check false-completion studies of Claude Code
(h-a-forster/overclaim) and a preregistered signed-record referee with a final-report measure (Truthgate,
Cygnux Labs); tasks that cannot be completed as asked (ImpossibleBench); reports that contradict the agent's
own transcript (OverclaimBench); a vendor's planted-blocker evaluation. What we did not find elsewhere is the
narrow combination here: the acting agent's own multi-key declaration, scored per key against harness
facts, with records a stranger can re-derive. That statement rests on a search made on 2026-11-21 in which
several paper hosts could not be opened; it should be re-checked before it is repeated anywhere.

Modules: ``tasks`` (the task format and sandboxes), ``collect`` (facts), ``score`` (the comparison),
``records`` (session and run records, ``rederive``), ``scripted`` and ``known_answers`` (the scorer's own
known-answer battery).
"""
from __future__ import annotations

# The submodules `collect` and `score` each hold a function of the same name, so the functions are not
# re-exported here: `from styxx.selfreport.collect import collect`, `from styxx.selfreport.score import score`.
from . import collect, known_answers, records, score, scripted, tasks
from .score import REQUIRED_KEYS
from .tasks import TaskError, default_tasks_root, list_tasks, load_task, materialise

__all__ = [
    "REQUIRED_KEYS", "TaskError", "collect", "default_tasks_root", "known_answers", "list_tasks", "load_task",
    "materialise", "records", "score", "scripted", "tasks",
]
