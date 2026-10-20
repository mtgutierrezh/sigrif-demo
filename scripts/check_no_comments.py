import pathlib
import sys
import tokenize

failures = []
for root in ("src", "tests", "scripts"):
    for path in pathlib.Path(root).rglob("*.py"):
        with path.open("rb") as handle:
            for token in tokenize.tokenize(handle.readline):
                if token.type == tokenize.COMMENT:
                    failures.append(f"{path}:{token.start[0]}: {token.string}")
if failures:
    print("\n".join(failures))
    sys.exit(1)
print("ok")
