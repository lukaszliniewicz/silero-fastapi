import sys

from silero_fastapi.cli import main


if __name__ == "__main__":
    main(["serve", *sys.argv[1:]])
