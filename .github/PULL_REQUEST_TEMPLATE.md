<!--
Thanks for contributing to Hardflow! Please keep PRs to one feature/fix each.
See CONTRIBUTING.md for the architecture rules.
-->

## What does this PR do?

<!-- A short description. Link the issue it closes, e.g. "Closes #12". -->

## Type of change

- [ ] Bug fix
- [ ] New feature / tool
- [ ] Docs only
- [ ] Refactor / cleanup

## Checklist

- [ ] New classes are added to the `_classes` tuple in `__init__.py`
- [ ] Logic lives in a pure `core/` function; the operator stays thin
- [ ] `core/` does not import `bpy.ops` / `gpu` / `blf` (boolean.py exception aside)
- [ ] Added/updated a test (`tests/test_core.py` for pure logic, `tests/test_blender.py` for bpy paths)
- [ ] `python tests/test_core.py` passes locally
- [ ] Updated the README key table if I added a user-facing action
- [ ] Checked the matching box in `ROADMAP.md` if applicable
- [ ] Code is PEP 8, ~90-char lines; comments/docstrings in English

## Verified in Blender?

<!-- Modal tools (draw, Push/Pull, Offset, pie/menu) need a live click-through;
     the headless suite can't reach them. See tests/manual_checklist.md. -->

- [ ] Tested by hand in Blender 4.2+ (describe what you clicked through)
- [ ] Not applicable / pure-core only
