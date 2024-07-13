import os
import sys
import matplotlib.pyplot as plt
from tree_sitter import Language

# Ensure the utils directory is in the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tree_sit import process_code_string

def read_test_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()

def test_parser(file_path, language_obj):
    test_results = {}
    error_reports = []

    try:
        file_content = read_test_file(file_path)
        node_tree = process_code_string(file_content, language_obj, file_path)
        test_results[file_path] = {
            'parsed_tree': node_tree,
            'success': True
        }
    except Exception as e:
        error_reports.append({
            'file_path': file_path,
            'error_message': str(e)
        })
        test_results[file_path] = {
            'parsed_tree': None,
            'success': False,
            'error_message': str(e)
        }

    return test_results, error_reports

def generate_report(test_results, error_reports):
    report = []

    for file_path, result in test_results.items():
        if result['success']:
            report.append(f"File: {file_path}\nParsing successful!\nParsed Tree:\n{result['parsed_tree']}\n")
        else:
            report.append(f"File: {file_path}\nParsing failed: {result['error_message']}\n")

    report.append("\nError Reports:\n")
    for error in error_reports:
        report.append(f"File: {error['file_path']}\nError: {error['error_message']}\n")

    report_path = "./unit_test/reports/tree_sitter_test_report.txt"
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as report_file:
        report_file.write("\n".join(report))

    print(f"Report generated: {report_path}")

def count_expected_elements(file_content, element):
    if element == 'classes':
        return file_content.count('class ') + file_content.count('struct ') + file_content.count('interface ') + file_content.count('enum ')
    elif element == 'imports':
        return file_content.count('import ')
    elif element == 'properties':
        return file_content.count('var ') + file_content.count('val ') + file_content.count('const ') + file_content.count('private ') + file_content.count('public ') + file_content.count('protected ')
    elif element == 'functions':
        return file_content.count('func ') + file_content.count('def ') + file_content.count('void ') + file_content.count('int ') + file_content.count('public ') + file_content.count('protected ') + file_content.count('private ')
    return 0

def calculate_accuracy(test_results):
    total_elements = {
        'classes': 0,
        'imports': 0,
        'properties': 0,
        'functions': 0
    }
    correct_elements = {
        'classes': 0,
        'imports': 0,
        'properties': 0,
        'functions': 0
    }

    for file_path, result in test_results.items():
        if result['success']:
            parsed_tree = result['parsed_tree']
            # Extract expected counts from the original content
            with open(file_path, 'r') as file:
                file_content = file.read()
                for element in total_elements:
                    total_elements[element] += count_expected_elements(file_content, element)

                correct_elements['classes'] += len(parsed_tree.class_names)
                correct_elements['imports'] += len(parsed_tree.imports)
                correct_elements['properties'] += len(parsed_tree.property_declarations)
                correct_elements['functions'] += len(parsed_tree.functions)

    accuracy = {element: (correct_elements[element] / total_elements[element]) * 100 if total_elements[element] else 0 for element in total_elements}

    # Ensure accuracy values are between 0 and 100
    accuracy = {k: min(100, max(0, v)) for k, v in accuracy.items()}

    return accuracy

def plot_accuracy(accuracy):
    categories = list(accuracy.keys())
    values = list(accuracy.values())

    plt.figure(figsize=(10, 6))
    plt.bar(categories, values, color=['blue', 'orange', 'green', 'red'])
    plt.ylim(0, 100)
    plt.ylabel('Accuracy (%)')
    plt.title('Parsing Accuracy by Category')

    # Save the plot as a PNG file
    plot_path = "./unit_test/reports/accuracy_plot.png"
    os.makedirs(os.path.dirname(plot_path), exist_ok=True)
    plt.savefig(plot_path)
    print(f"Plot saved: {plot_path}")

    plt.show()

if __name__ == "__main__":
    test_files_directory = "./unit_test/test_content/"
    so_file_path = os.path.abspath("./grammar_utils/language_grammars.so")
    extension_to_language = {
        "swift": (Language(so_file_path, "swift"), "swift_code.txt"),
        "c": (Language(so_file_path, "c"), "c_code.txt"),
        "java": (Language(so_file_path, "java"), "java_code.txt"),
        "kotlin": (Language(so_file_path, "kotlin"), "kotlin_code.txt"),
        "javascript": (Language(so_file_path, "javascript"), "js_code.txt"),
        "go": (Language(so_file_path, "go"), "go_code.txt"),
        "python": (Language(so_file_path, "python"), "python_code.txt"),
        "cpp": (Language(so_file_path, "cpp"), "cpp_code.txt"),
    }

    all_results = {}
    all_errors = []

    for lang, (language_obj, test_file) in extension_to_language.items():
        file_path = os.path.join(test_files_directory, test_file)
        results, errors = test_parser(file_path, language_obj)
        all_results.update(results)
        all_errors.extend(errors)

    generate_report(all_results, all_errors)

    accuracy = calculate_accuracy(all_results)
    plot_accuracy(accuracy)
    print("Accuracy:", accuracy)
