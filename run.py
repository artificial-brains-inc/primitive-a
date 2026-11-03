"""Application entry point discovered by ab run -ab --env .env."""
from avoidance.application import main

if __name__ == "__main__":
    raise SystemExit(main())
