# Milestone 2 package cleanup

This repack removes cache artifacts from the release package.

Removed patterns:
- `.pytest_cache/`
- `.ruff_cache/`
- `__pycache__/`
- `*.pyc`

Removed files: 33

- `.pytest_cache/.gitignore`
- `.pytest_cache/CACHEDIR.TAG`
- `.pytest_cache/README.md`
- `.pytest_cache/v/cache/nodeids`
- `.ruff_cache/.gitignore`
- `.ruff_cache/0.15.6/13143642518470014447`
- `.ruff_cache/0.15.6/14910896774447423245`
- `.ruff_cache/0.15.6/808382604929530084`
- `.ruff_cache/CACHEDIR.TAG`
- `src/start_here_extractor/__pycache__/__init__.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/av.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/batch.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/cli.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/errors.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/extractor.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/inspector.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/jsonl.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/locator.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/matcher.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/processor.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/reader.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/reporter.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/types.cpython-313.pyc`
- `src/start_here_extractor/__pycache__/utils.cpython-313.pyc`
- `src/start_here_extractor/cloud/__pycache__/__init__.cpython-313.pyc`
- `src/start_here_extractor/cloud/__pycache__/base.cpython-313.pyc`
- `src/start_here_extractor/cloud/__pycache__/dropbox_stub.cpython-313.pyc`
- `src/start_here_extractor/cloud/__pycache__/gdrive_stub.cpython-313.pyc`
- `src/start_here_extractor/cloud/__pycache__/graph_stub.cpython-313.pyc`
- `tests/__pycache__/test_batch_ordering.cpython-313-pytest-9.0.2.pyc`
- `tests/__pycache__/test_cloud_stubs.cpython-313-pytest-9.0.2.pyc`
- `tests/__pycache__/test_jsonl.cpython-313-pytest-9.0.2.pyc`
- `tests/__pycache__/test_milestone1.cpython-313-pytest-9.0.2.pyc`
