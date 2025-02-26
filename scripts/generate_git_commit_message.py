import git
import os
from datetime import datetime

def get_git_changes(repo_path):
    repo = git.Repo(repo_path)
    changed_files = [item.a_path for item in repo.index.diff(None)]
    return changed_files

def generate_commit_message(changed_files):
    commit_message = "### Changes made:\n\n"
    for file in changed_files:
        commit_message += f"- {file}\n"
    
    commit_message += "\n### Detailed changes:\n\n"
    for file in changed_files:
        commit_message += f"#### {file}\n"
        commit_message += get_file_diff(file)
        commit_message += "\n"
    
    return commit_message

def get_file_diff(file_path):
    repo = git.Repo(os.getcwd())
    diff = repo.git.diff('HEAD', file_path)
    return diff

def prepend_to_changelog(new_content):
    changelog_path = "CHANGELOG.md"
    if os.path.exists(changelog_path):
        with open(changelog_path, "r") as f:
            existing_content = f.read()
    else:
        existing_content = ""

    with open(changelog_path, "w") as f:
        f.write(new_content + "\n\n" + existing_content)

def main():
    repo_path = os.getcwd()
    changed_files = get_git_changes(repo_path)
    commit_message = generate_commit_message(changed_files)
    
    generated_on = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_content = f"---\nGenerated on: {generated_on}\n\n{commit_message}"
    
    prepend_to_changelog(new_content)

if __name__ == "__main__":
    main()