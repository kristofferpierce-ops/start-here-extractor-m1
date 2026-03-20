# M4D version metadata fix

This patch corrects the runtime version metadata so inventory `run.version` matches the installed package version `0.8.0`.

## Changed file
- `src/start_here_extractor/__init__.py`

## Why
The package metadata and editable install reported `0.8.0`, but runtime records still imported `__version__ = "0.7.2"`, which caused audit and monitoring records to report the wrong version.
