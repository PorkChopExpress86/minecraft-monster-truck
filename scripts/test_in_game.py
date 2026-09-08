"""Compatibility entry point for the verified runner; use Test-Addon.ps1 for setup."""
import sys

if __package__:
    from .bedrock_test import main
else:
    from bedrock_test import main


if __name__ == "__main__":
    # The former dry-run could modify packs and report an unverified pass.
    if sys.argv[1:] == ["--dry-run"]:
        sys.exit(main(["doctor"]))
    sys.exit(main(["game", *sys.argv[1:]]))
