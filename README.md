# crawler_exercise
A simple web crawler built as an interview exercise, using Python 3, `asyncio`, and `aiohttp`.

# Installation

```bash
# (git clone...)
cd crawler_exercise

# create an isolated environment in which to install dependencies
# (this will avoid conflicts with system-wide libraries):
python3 -m venv env && source env/bin/activate

# install dependencies:
python3 -m pip install -r requirements.txt
```

# Running

```bash
./main.py http://spacejam.com
# or
./main.py http://spacejam.com --debug
```

The script will output URLs it visits (not indented) as well as links it finds on those pages (indented).

To run the test:

```bash
./test.py
```
