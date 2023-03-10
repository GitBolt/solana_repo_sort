import os
import csv
import time
import itertools
import pygsheets
from github import Github
from dotenv import load_dotenv

load_dotenv()

github_key = os.getenv('GH_KEY')
github_key2 = os.getenv('GH_KEY2')

# Input data file name
data_file = "repos.csv"
# The classification type column letter in spreadsheet
column_letter = "L"
# Start at the specified repo index from csv (to pause/resume)
continue_num = 0

# Tags for classification
solana_tag = "PASS"
multichain_tag = "MULTI"
private_tag = "PRIVATE"
invalid_tag = "FAIL"

# Spreadsheet details
name = "Audited [By Bolt]"
sheet_title = "repos"

repos = []

with open(data_file, 'r') as file:
    reader = csv.reader(file)
    for row in reader:
        if row and row[0].startswith('http'):
            repos.append(str(row[0]))


# List of Solana keywords and libs to check for in package files
sol_keywords = [
    "@solana/web3.js",
    "@metaplex-foundation",
    "@solana/spl-token",
    "@project-serum/anchor",
    "francium-sdk",
    "anchor-lang",
    "anchor-spl",
    "spl-token",
    "@coral-xyz/",
    "react-xnft",
    "solana-program",
    "solana",
    "metaplex",
    "spl",
    "serum-dex",
]

# Other chain keywords and libs
other_keywords = [
    '"web3.js"',
    "ethers.js",
    "solidity",
    "ethereum",
    "cardano",
    "tezos",
    "polygon",
    "matic",
    "hardhat",
    "ethers",
    "monero",
    "bitcoin",
    "eth-",
    "metamask",
    "aptos",
    "brave-wallet",
]

ignore_dirs = [
    "node_modules",
    ".vscode",
    ".github",
    ".husky",
    ".git",
    ".idea",
    ".cache",
    ".DS_Store",
]


# Initialize the Google Sheets client
client = pygsheets.authorize(service_account_file="credentials.json")
spreadsheet = client.open(name)
worksheet = spreadsheet.worksheet("title", sheet_title)


def identify(repo_url: str) -> str:
    given_type = private_tag
    repo_data = None

    gh = Github(github_key)

    repo_name = repo_url.split("github.com/")[1].strip()
    try:
        repoData = gh.get_repo(repo_name)
    except Exception as e:
        # If rate limited, switch to other key
        if ("API rate" in str(e)):
            print("You got rate limited nerd")
            gh = Github(github_key2)
            repo_data = gh.get_repo(repo_name)
        else:
            # Repo private most likely
            given_type = private_tag
            return given_type

    print(f"Checking: {repo} at cell {column_letter}{continue_num+idx+2}")
    if repoData:
        # Repo is not private anymore, but invalid without checks yet
        given_type = invalid_tag

        content = repoData.get_contents("")

        # Check subdirectories for package.json and Cargo.toml
        content.extend(
            c
            for i in content
            if i.type == "dir" and i.name not in ignore_dirs
            for c in repoData.get_contents(i.path)
            if c.name in ["package.json", "Cargo.toml", "go.mod", "setup.py"]
        )

        content.extend(
            c
            for i in content
            if i.type == "dir" and i.name not in ignore_dirs
            for i2 in repoData.get_contents(i.path)
            if i2.type == "dir"
            for c in repoData.get_contents(i2.path)
            if c.name in ["package.json", "Cargo.toml", "go.mod", "setup.py"]
        )

        packages = [c for c in content if c.name.lower() == "package.json"]
        tomls = [c for c in content if c.name.lower() == "cargo.toml"]
        go_libs = [c for c in content if c.name.lower() == "go.mod"]
        pysetups = [c for c in content if c.name.lower() == "setup.py"]


        for content in itertools.chain(
            packages,
            tomls,
            go_libs,
            pysetups
        ):
            decoded_content = content.decoded_content.decode("utf-8")
            if any(ext in decoded_content for ext in sol_keywords):
                if content in packages:
                    print("SOL [From package.json]")
                elif content in tomls:
                    print("SOL [From Cargo.toml")
                elif content in go_libs:
                    print("SOL [From go.mod")
                elif content in pysetups:
                    print("SOL [From setup.py]")
                given_type = solana_tag
                break
            else:
                print(decoded_content)

        # Multi chain check
        for item in itertools.chain(packages, go_libs, tomls, pysetups):
            if hasattr(item, "decoded_content") and any(ext in item.decoded_content.decode("utf-8") for ext in other_keywords):
                matching_keywords = [
                    ext for ext in other_keywords if ext in item.decoded_content.decode("utf-8")
                ]
                print(f"These matched: {matching_keywords}")
                if given_type == solana_tag:
                    given_type = multichain_tag
                else:
                    given_type = invalid_tag
                    print(f"Found other chain [From {item.filename}]")
                break

    else:
        print("Repo data not found")
        given_type = invalid_tag

    return given_type


for idx, repo in enumerate(repos[continue_num:]):
    try:
        given_type = identify(repo)
        row = column_letter + str(idx + continue_num + 2)
        worksheet.update_values(row, [[given_type]])
        print(
            f"Updated {column_letter}{continue_num+idx+2} with {given_type}\n")
    except Exception as e:
        print(e)
        continue
print("Finished.")
