import os
import subprocess
import sys
from tree_sitter import Language

repos = []
with open("language_grammar_repos.txt", "r") as file:
    for line in file:
        url, ref = line.split()
        clone_directory = os.path.join("vendor", url.rstrip("/").split("/")[-1])
        repos.append((url, ref, clone_directory))

# During the build, this script runs several times, and only needs to download
# repositories on first time.
if os.path.isdir("vendor") and len(os.listdir("vendor")) == len(repos):
    print(f"{sys.argv[0]}: Language repositories have been cloned already.")
else:
    os.makedirs("vendor", exist_ok=True)
    for url, ref, clone_directory in repos:
        print()
        print(f"{sys.argv[0]}: Cloning: {url} (ref {ref}) --> {clone_directory}")
        print()

        if os.path.exists(clone_directory):
            continue

        # https://serverfault.com/a/713065
        os.mkdir(clone_directory)
        subprocess.check_call(["git", "init"], cwd=clone_directory)
        subprocess.check_call(["git", "remote", "add", "origin", url], cwd=clone_directory)
        subprocess.check_call(["git", "fetch", "--depth=1", "origin", ref], cwd=clone_directory)
        subprocess.check_call(["git", "checkout", ref], cwd=clone_directory)

# Ensure the src directory exists for all parsers
for url, ref, clone_directory in repos:
    if "tree-sitter-swift" in url:
        swift_src_dir = os.path.join(clone_directory, "src")
        if not os.path.exists(swift_src_dir):
            print(f"Cloning and generating files for {url}")
            if not os.path.exists(clone_directory):
                os.mkdir(clone_directory)
                subprocess.check_call(["git", "init"], cwd=clone_directory)
                subprocess.check_call(["git", "remote", "add", "origin", url], cwd=clone_directory)
                subprocess.check_call(["git", "fetch", "--depth=1", "origin", ref], cwd=clone_directory)
                subprocess.check_call(["git", "checkout", ref], cwd=clone_directory)
            subprocess.check_call(["npm", "install"], cwd=clone_directory)
            subprocess.check_call(["npm", "run", "generate"], cwd=clone_directory)

print()

if sys.platform == "win32":
    languages_filename = "tree_sitter_languages\\languages.dll"
else:
    languages_filename = "tree_sitter_languages/languages.so"

print(f"{sys.argv[0]}: Building", languages_filename)

# Ensure tree-sitter headers are included in the search path
include_dir = "/usr/local/include"
if sys.platform == "darwin":
    include_dir = "/opt/homebrew/include"

try:
    Language.build_library(
        languages_filename,
        [
            'vendor/tree-sitter-bash',
            'vendor/tree-sitter-c',
            'vendor/tree-sitter-c-sharp',
            'vendor/tree-sitter-cpp',
            'vendor/tree-sitter-css',
            'vendor/tree-sitter-go',
            'vendor/tree-sitter-html',
            'vendor/tree-sitter-java',
            'vendor/tree-sitter-javascript',
            'vendor/tree-sitter-jsdoc',
            'vendor/tree-sitter-json',
            'vendor/tree-sitter-kotlin',
            'vendor/tree-sitter-python',
            'vendor/tree-sitter-regex',
            'vendor/tree-sitter-ruby',
            'vendor/tree-sitter-rust',
            'vendor/tree-sitter-scala',
            'vendor/tree-sitter-toml',
            'vendor/tree-sitter-swift'  # Ensure Swift parser is included here
        ]
    )
except Exception as e:
    print(f"Error during build: {e}")
    sys.exit(1)
