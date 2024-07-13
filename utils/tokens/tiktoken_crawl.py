import os
import logging
import matplotlib.pyplot as plt
import tiktoken

# Initialize tiktoken encoder
enc = tiktoken.encoding_for_model("gpt-4")

# Supported language extensions
LANGUAGE_DATA = {
    "java": ("java", [".java"]),
    "kotlin": ("kotlin", [".kt"]),
    "javascript": ("javascript", [".js", ".jsx"]),
    "go": ("go", [".go"]),
    "python": ("python", [".py"]),
    "cpp": ("cpp", [".cpp", ".cc", ".cxx"]),
    "c": ("c", [".c"]),
    "swift": ("swift", [".swift"])
}

def count_tokens(text):
    return len(enc.encode(text))

def chunk_text(text, tokens_per_chunk=500):
    words = text.split()
    return [' '.join(words[i:i+tokens_per_chunk]) for i in range(0, len(words), tokens_per_chunk)]

def get_file_size(file_path):
    return os.path.getsize(file_path)

def is_supported_file(file_path):
    _, ext = os.path.splitext(file_path)
    for lang, (_, exts) in LANGUAGE_DATA.items():
        if ext in exts:
            return True
    return False

def process_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        total_tokens = 0
        chunks = chunk_text(content)
        for chunk in chunks:
            total_tokens += count_tokens(chunk)
        return total_tokens
    except Exception as e:
        logging.error(f"Error processing file {file_path}: {e}")
        return 0

def find_largest_file_and_collect_metrics(root_dir):
    largest_file = None
    largest_size = 0
    total_tokens = 0
    total_files = 0
    total_token_count = 0
    file_token_counts = []
    file_sizes = []

    project_paths = [os.path.join(root_dir, d) for d in os.listdir(root_dir) if os.path.isdir(os.path.join(root_dir, d)) and not should_skip_path(os.path.join(root_dir, d))]
    total_projects = len(project_paths)

    for i, project_path in enumerate(project_paths, start=1):
        logging.info(f"Processing project {i}/{total_projects}")
        for root, _, files in os.walk(project_path):
            for file in files:
                file_path = os.path.join(root, file)
                if should_skip_path(file_path) or not is_supported_file(file_path):
                    continue
                file_size = get_file_size(file_path)
                file_tokens = process_file(file_path)
                total_token_count += file_tokens
                total_files += 1
                file_token_counts.append((file_path, file_tokens))
                file_sizes.append(file_size)
                if file_size > largest_size:
                    largest_file = file_path
                    largest_size = file_size
                    total_tokens = file_tokens

    average_tokens_per_file = total_token_count / total_files if total_files > 0 else 0

    return largest_file, total_tokens, total_files, total_token_count, average_tokens_per_file, file_token_counts

def should_skip_path(path):
    skip_directories = [
        'node_modules', 'build', 'dist', 'out', 'bin', '.git', '.svn', '.vscode',
        '__pycache__', '.idea', 'obj', 'lib', 'vendor', 'target', '.next', 'pkg',
        'venv', '.tox', 'wheels', 'Debug', 'Release', 'deps'
    ]
    return any(skip_dir in path.split(os.path.sep) for skip_dir in skip_directories)

def calculate_percentages(file_token_counts, thresholds):
    counts = {}
    total_files = len(file_token_counts)
    for threshold in thresholds:
        counts[threshold] = sum(1 for _, tokens in file_token_counts if tokens < threshold)
    percentages = {threshold: (count / total_files) * 100 for threshold, count in counts.items()}
    return percentages, counts

def plot_file_tokens(file_token_counts, percentages, counts):
    file_paths, token_counts = zip(*file_token_counts)
    within_limit_counts = [tokens for tokens in token_counts if tokens <= 100000]
    over_limit_counts = [tokens for tokens in token_counts if tokens > 100000]

    fig, ax = plt.subplots(2, 1, figsize=(20, 12))
    figManager = plt.get_current_fig_manager()
    figManager.full_screen_toggle()

    # Histogram for files within 100k tokens
    ax[0].hist(within_limit_counts, bins=50, color='blue', edgecolor='black', alpha=0.7, label='<= 100k tokens')
    # Scatter plot for outliers
    outlier_indices = [i for i, tokens in enumerate(token_counts) if tokens > 100000]
    outlier_tokens = [token_counts[i] for i in outlier_indices]
    ax[0].scatter(outlier_indices, outlier_tokens, color='red', label='> 100k tokens')

    # Add a line at the 100k token limit
    ax[0].axhline(100000, color='grey', linestyle='--', label='100k tokens limit')

    ax[0].set_ylim(0, 200000)
    ax[0].set_yticks(range(0, 200001, 20000))
    ax[0].set_title('File Token Counts')
    ax[0].set_xlabel('File Index')
    ax[0].set_ylabel('Token Count')
    ax[0].legend()
    ax[0].grid(True)

    # Pie chart for percentage of files within thresholds
    thresholds = [100000, 75000, 50000, 25000, 10000, 5000]
    sizes = [counts[threshold] - counts[thresholds[i + 1]] if i < len(thresholds) - 1 else counts[threshold] for i, threshold in enumerate(thresholds)] + [len(file_token_counts) - counts[thresholds[0]]]
    labels = [f'< {threshold // 1000}k tokens' for threshold in thresholds] + [f'>= {thresholds[0] // 1000}k tokens']
    colors = ['blue', 'green', 'yellow', 'orange', 'purple', 'pink', 'red']

    ax[1].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=140)
    ax[1].set_title('Percentage of Files Within Token Count Thresholds')

    plt.tight_layout()
    plt.show()

    # Print percentages for each threshold
    for threshold, percentage in percentages.items():
        print(f"{percentage:.2f}% of files have less than {threshold} tokens")

    # Print outliers details
    print("\nOutliers (files with > 100k tokens):")
    for path, tokens in zip(file_paths, token_counts):
        if tokens > 100000:
            print(f"{path}: {tokens} tokens")

def main(root_dir):
    thresholds = [100000, 75000, 50000, 25000, 10000, 5000]
    largest_file, total_tokens, total_files, total_token_count, average_tokens_per_file, file_token_counts = find_largest_file_and_collect_metrics(root_dir)
    percentages, counts = calculate_percentages(file_token_counts, thresholds)

    print(f"Largest file: {largest_file}")
    print(f"Total tokens in the largest file: {total_tokens}")
    print(f"Total files processed: {total_files}")
    print(f"Total tokens across all files: {total_token_count}")
    print(f"Average tokens per file: {average_tokens_per_file}")

    for threshold, percentage in percentages.items():
        print(f"{percentage:.2f}% of files have less than {threshold} tokens")

    plot_file_tokens(file_token_counts, percentages, counts)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    root_dir = "/Users/z98459/Desktop/wsb_android/"
    main(root_dir)
