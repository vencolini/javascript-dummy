import os
import subprocess
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration Variables
PROJECT_NAME = "JavaScript-Project"  # Name of the project directory
START_DAYS_AGO = 1095  # 3 years 1095 days # How far back to start (in days) 
MAX_COMMITS_PER_DAY = 10

# Fetch GitHub details from environment variables
GITHUB_NAME = os.getenv("GITHUB_NAME")
GITHUB_EMAIL = os.getenv("GITHUB_EMAIL")

if not GITHUB_NAME or not GITHUB_EMAIL:
    raise ValueError("Please set the GITHUB_NAME and GITHUB_EMAIL environment variables.")

FILE_CHANGES = [
    ("index.html", "<!DOCTYPE html>\n<html>\n<head>\n    <title>Dummy Project</title>\n    <link rel='stylesheet' href='styles.css'>\n</head>\n<body>\n    <h1>Hello World</h1>\n    <script src='script.js'></script>\n</body>\n</html>"),
    ("styles.css", "body { font-family: Arial, sans-serif; }\nh1 { color: #333; }"),
    ("script.js", "console.log('Hello World');")
]

def run_command(cmd, cwd=None):
    """Run a shell command."""
    result = subprocess.run(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        print(f"Error running command: {cmd}\n{result.stderr.decode()}")
    return result.stdout.decode()

def initialize_git(repo_path):
    """Initialize a git repository."""
    run_command("git init", cwd=repo_path)
    run_command(f"git config user.name \"{GITHUB_NAME}\"", cwd=repo_path)
    run_command(f"git config user.email \"{GITHUB_EMAIL}\"", cwd=repo_path)

def create_files(repo_path):
    """Create initial project files."""
    for filename, content in FILE_CHANGES:
        with open(os.path.join(repo_path, filename), 'w') as f:
            f.write(content)

def make_commit(repo_path, commit_date):
    """Make a dummy commit with a specific date."""
    # Modify a file slightly to ensure Git detects a change
    filename, _ = random.choice(FILE_CHANGES)
    file_path = os.path.join(repo_path, filename)
    with open(file_path, 'a') as f:
        f.write(f"\n// Commit on {commit_date}\n")
    
    run_command("git add .", cwd=repo_path)
    
    env = os.environ.copy()
    env['GIT_AUTHOR_DATE'] = commit_date
    env['GIT_COMMITTER_DATE'] = commit_date
    
    commit_message = f"Dummy commit on {commit_date}"
    subprocess.run(f'git commit -m "{commit_message}" --date "{commit_date}"', shell=True, cwd=repo_path, env=env)

def generate_commits(repo_path, start_date):
    """Generate commits from start_date to today."""
    today = datetime.today()
    current_date = start_date
    while current_date <= today:
        # Decide randomly whether to have commits on this day
        if random.choice([True, False, True]):  # More likely to have commits
            num_commits = random.randint(1, MAX_COMMITS_PER_DAY)
            for _ in range(num_commits):
                # Randomize the time within the day
                commit_time = current_date + timedelta(
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59),
                    seconds=random.randint(0, 59)
                )
                commit_date = commit_time.strftime('%Y-%m-%dT%H:%M:%S')
                make_commit(repo_path, commit_date)
        # Move to next day
        current_date += timedelta(days=1)

def main():
    # Define the project path
    current_dir = os.getcwd()
    repo_path = os.path.join(current_dir, PROJECT_NAME)
    
    # Create project directory
    os.makedirs(repo_path, exist_ok=True)
    
    # Initialize Git
    initialize_git(repo_path)
    
    # Create initial files and initial commit
    create_files(repo_path)
    initial_commit_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%dT12:00:00')
    make_commit(repo_path, initial_commit_date)
    
    # Generate backdated commits
    start_date = datetime.today() - timedelta(days=START_DAYS_AGO)
    generate_commits(repo_path, start_date)
    
    print(f"Dummy project created at {repo_path}")
    print("You can now navigate to the project directory and push it to GitHub.")

if __name__ == "__main__":
    main()