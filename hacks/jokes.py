import random, json, os, fcntl
from flask import current_app

jokes_data = []
joke_list = [
    "If you give someone a program... you will frustrate them for a day; if you teach them how to program... you will "
    "frustrate them for a lifetime.",
    "Q: Why did I divide sin by tan? A: Just cos.",
    "UNIX is basically a simple operating system... but you have to be a genius to understand the simplicity.",
    "Enter any 11-digit prime number to continue.",
    "If at first you don't succeed; call it version 1.0.",
    "Java programmers are some of the most materialistic people I know, very object-oriented",
    "The oldest computer can be traced back to Adam and Eve. It was an apple but with extremely limited memory. Just "
    "1 byte. And then everything crashed.",
    "Q: Why did Wi-Fi and the computer get married? A: Because they had a connection",
    "Bill Gates teaches a kindergarten class to count to ten. 1, 2, 3, 3.1, 95, 98, ME, 2000, XP, Vista, 7, 8, 10.",
    "Q: What’s a aliens favorite computer key? A: the space bar!",
    "There are 10 types of people in the world: those who understand binary, and those who don’t.",
    "If it wasn't for C, we’d all be programming in BASI and OBOL.",
    "Computers make very fast, very accurate mistakes.",
    "Q: Why is it that programmers always confuse Halloween with Christmas? A: Because 31 OCT = 25 DEC.",
    "Q: How many programmers does it take to change a light bulb? A: None. It’s a hardware problem.",
    "The programmer got stuck in the shower because the instructions on the shampoo bottle said: Lather, Rinse, Repeat.",
    "Q: What is the biggest lie in the entire universe? A: I have read and agree to the Terms and Conditions.",
    'An SQL statement walks into a bar and sees two tables. It approaches, and asks may I join you?'
]

def get_jokes_file():
    # Always use Flask app.config['DATA_FOLDER'] for shared data
    data_folder = current_app.config['DATA_FOLDER']
    return os.path.join(data_folder, 'jokes.json')

def _read_jokes_file():
    JOKES_FILE = get_jokes_file()
    if not os.path.exists(JOKES_FILE):
        return []
    with open(JOKES_FILE, 'r') as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            data = json.load(f)
        except Exception:
            data = []
        fcntl.flock(f, fcntl.LOCK_UN)
    return data

def _write_jokes_file(data):
    JOKES_FILE = get_jokes_file()
    with open(JOKES_FILE, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f)
        fcntl.flock(f, fcntl.LOCK_UN)

def initJokes():
    JOKES_FILE = get_jokes_file()
    # Only initialize if file does not exist
    if os.path.exists(JOKES_FILE):
        return
    jokes_data = []
    item_id = 0
    for item in joke_list:
        jokes_data.append({"id": item_id, "joke": item, "haha": 0, "boohoo": 0})
        item_id += 1
    # prime some haha responses
    for i in range(10):
        id = random.choice(jokes_data)['id']
        jokes_data[id]['haha'] += 1
    for i in range(5):
        id = random.choice(jokes_data)['id']
        jokes_data[id]['boohoo'] += 1
    _write_jokes_file(jokes_data)
        
def getJokes():
    return _read_jokes_file()

def getJoke(id):
    jokes = _read_jokes_file()
    return jokes[id]

def getRandomJoke():
    jokes = _read_jokes_file()
    return random.choice(jokes)

def favoriteJoke():
    jokes = _read_jokes_file()
    best = 0
    bestID = -1
    for joke in jokes:
        if joke['haha'] > best:
            best = joke['haha']
            bestID = joke['id']
    return jokes[bestID] if bestID != -1 else None
    
def jeeredJoke():
    jokes = _read_jokes_file()
    worst = 0
    worstID = -1
    for joke in jokes:
        if joke['boohoo'] > worst:
            worst = joke['boohoo']
            worstID = joke['id']
    return jokes[worstID] if worstID != -1 else None


# Atomic vote update with exclusive lock
def _vote_joke(id, field):
    JOKES_FILE = get_jokes_file()
    with open(JOKES_FILE, 'r+') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        jokes = json.load(f)
        jokes[id][field] += 1
        # Move file pointer to start before writing updated JSON
        f.seek(0)
        json.dump(jokes, f)
        # Truncate file to remove any leftover data from previous content
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)
    return jokes[id][field]

def addJokeHaHa(id):
    return _vote_joke(id, 'haha')

def addJokeBooHoo(id):
    return _vote_joke(id, 'boohoo')

def printJoke(joke):
    print(joke['id'], joke['joke'], "\n", "haha:", joke['haha'], "\n", "boohoo:", joke['boohoo'], "\n")

def countJokes():
    jokes = _read_jokes_file()
    return len(jokes)

if __name__ == "__main__": 
    initJokes()  # initialize jokes
    
    # Most likes and most jeered
    best = favoriteJoke()
    if best:
        print("Most liked", best['haha'])
        printJoke(best)
    worst = jeeredJoke()
    if worst:
        print("Most jeered", worst['boohoo'])
        printJoke(worst)
    
    # Random joke
    print("Random joke")
    printJoke(getRandomJoke())
    
    # Count of Jokes
    print("Jokes Count: " + str(countJokes()))