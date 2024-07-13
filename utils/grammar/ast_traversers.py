import json
import re

############################################################################
############################################################################
######        CUSTOM, PAINSTANKELY WRITTEN AST TRAVERSERS             ######
######                                                                ######
###### - create similar ones for the language you'd like to support - ######
######  detailed instructions can be found at:                        ######
######          [utils/grammar/so, what is this .so file?]            ######
######                                                                ######
############################################################################
############################################################################

def traverse_tree_java(node, code, node_tree, language):
    java_function = None
    query_string = """
    (import_declaration) @import
    (package_declaration) @package
    (class_declaration name: (identifier) @name) @class
    (annotation) @annotation
    (interface_declaration name: (identifier) @name) @interface
    (field_declaration) @field
    (method_declaration) @method
    """

    query = language.query(query_string)
    captures = query.captures(node)

    should_traverse_children = True
    for capture_node, capture_name in captures:
        if capture_node == node:
            should_traverse_children = False

    for capture_node, capture_index in captures:
        if capture_index == "import":
            node_tree.imports.append(
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            )

        elif capture_index == "package":
            node_tree.package = (
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            )

        elif capture_index in ["class", "class_public", "class_abstract"]:
            class_name_match = re.search(
                r"\b(?:class|interface)\s+([a-zA-Z_]\w*)",
                code[capture_node.start_byte : capture_node.end_byte].decode("utf-8"),
            )
            if class_name_match:
                class_name = class_name_match.group(1)
                node_tree.class_names.append(class_name)

        elif capture_index == "field":
            property_declaration = (
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            )
            node_tree.property_declarations.append(property_declaration)

        elif capture_index == "annotation":
            annotation_text = (
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            )
            if java_function:
                java_function.annotations.append(annotation_text)

        elif capture_index == "method":
            method_code = code[capture_node.start_byte : capture_node.end_byte].decode(
                "utf-8"
            )
            func_name_match = re.search(
                r"\b(?:public|protected|private|static|final|abstract|synchronized|native|strictfp)?\s*(\w+\s+)?(\w+)\s*\(",
                method_code,
            )
            if func_name_match:
                return_type = func_name_match.group(1).strip() if func_name_match.group(1) else "void"
                func_name = func_name_match.group(2).strip()
                parameters_match = re.search(r'\((.*?)\)', method_code)
                parameters = parameters_match.group(1).strip() if parameters_match else ""
                func_body_match = re.search(r'\{(.*)\}', method_code, re.DOTALL)
                func_body = func_body_match.group(1).strip() if func_body_match else ""

                java_function = FunctionNode(
                    name=func_name,
                    parameters=parameters.split(",") if parameters else [],
                    return_type=return_type,
                    body=func_body,
                    class_names=node_tree.class_names,
                )

                duplicate_found = any(
                    func.name == java_function.name
                    and func.return_type == java_function.return_type
                    and func.parameters == java_function.parameters
                    for func in node_tree.functions
                )

                if not duplicate_found:
                    node_tree.functions.append(java_function)

    if should_traverse_children:
        for child_node in node.children:
            traverse_tree_java(child_node, code, node_tree, language)


def traverse_tree_c(node, code, node_tree, language):
    c_function = None
    query_string = """
    (preproc_include) @include
    (function_definition) @function
    (declaration) @variable
    (struct_specifier) @struct
    """
    query = language.query(query_string)
    captures = query.captures(node)

    should_traverse_children = True
    for capture_node, capture_name in captures:
        if capture_node == node:
            should_traverse_children = False

    for capture_node, capture_index in captures:
        text = code[capture_node.start_byte : capture_node.end_byte].decode("utf-8").strip()

        if capture_index == "include":
            node_tree.imports.append(text)
        elif capture_index == "function":
            function_details = extract_function_details_c(text)
            if function_details and not any(f.name == function_details.name for f in node_tree.functions):
                node_tree.functions.append(function_details)
        elif capture_index == "variable":
            # Consider global variables only if outside any function definition
            if not node_tree.functions:
                node_tree.property_declarations.append(text)
        elif capture_index == "struct":
            struct_name_match = re.search(r'struct\s+(\w+)', text)
            if struct_name_match:
                node_tree.class_names.append(struct_name_match.group(1))

    if should_traverse_children:
        for child in node.children:
            traverse_tree_c(child, code, node_tree, language)

def extract_function_details_c(text):
    func_name_match = re.search(r'(\w+)\s*\(', text)
    func_name = func_name_match.group(1) if func_name_match else "anonymous"
    parameters_match = re.search(r'\((.*?)\)', text)
    parameters = parameters_match.group(1).strip() if parameters_match else ""
    return_type_match = re.search(r'^(\w+)\s+', text)
    return_type = return_type_match.group(1).strip() if return_type_match else "int"  # Default return type in C is int
    func_body_match = re.search(r'\{\s*(.*?)\s*\}', text, re.DOTALL)
    func_body = func_body_match.group(1).strip() if func_body_match else ""

    return FunctionNode(
        name=func_name,
        parameters=parameters.split(",") if parameters else [],
        return_type=return_type,
        body=func_body
    )



def traverse_tree_cpp(node, code, node_tree, language):
    cpp_function = None
    query_string = """
    (preproc_include) @include
    (namespace_definition) @namespace
    (struct_specifier) @struct
    (class_specifier) @class
    (function_definition) @function
    (declaration) @field
    """
    query = language.query(query_string)
    captures = query.captures(node)

    should_traverse_children = True
    for capture_node, capture_name in captures:
        if capture_node == node:
            should_traverse_children = False

    for capture_node, capture_index in captures:
        text = code[capture_node.start_byte : capture_node.end_byte].decode("utf-8").strip()

        if capture_index == "include":
            node_tree.imports.append(text)
        elif capture_index == "namespace":
            # Assuming the namespace can be nested or complex, this simplifies to a single namespace string
            namespace_name_match = re.search(r'namespace\s+([\w:]+)', text)
            if namespace_name_match:
                node_tree.package = namespace_name_match.group(1)
        elif capture_index in ["class", "struct"]:
            class_or_struct_match = re.search(r'\b(class|struct)\s+([\w<>,\s]+)', text)
            if class_or_struct_match:
                node_tree.class_names.append(class_or_struct_match.group(2).strip())
        elif capture_index == "function":
            function_details = extract_function_details_cpp(text, node_tree.class_names)
            if function_details and not any(f.name == function_details.name for f in node_tree.functions):
                node_tree.functions.append(function_details)
        elif capture_index == "field":
            node_tree.property_declarations.append(text)

    if should_traverse_children:
        for child in node.children:
            traverse_tree_cpp(child, code, node_tree, language)

def extract_function_details_cpp(text, class_names):
    func_name_match = re.search(r'(\w+)\s*\((.*)\)\s*(const)?\s*{?', text)
    parameters = func_name_match.group(2).strip() if func_name_match else ""
    func_name = func_name_match.group(1) if func_name_match else ""
    return_type_match = re.search(r'\w+\s+(\w+)', text.split('(')[0])
    return_type = return_type_match.group(1).strip() if return_type_match else "void"
    func_body_match = re.search(r'\{(.*)\}', text, re.DOTALL)
    func_body = func_body_match.group(1).strip() if func_body_match else ""

    return FunctionNode(
        name=func_name,
        parameters=parameters.split(","),
        return_type=return_type,
        body=func_body,
        class_names=class_names
    )



def traverse_tree_go(node, code, node_tree, language):
    go_function = None
    query_string = """
    (import_declaration) @import
    (package_clause) @package
    (function_declaration) @function
    (method_declaration) @method
    (type_declaration) @type
    (var_declaration) @var
    """
    query = language.query(query_string)
    captures = query.captures(node)

    should_traverse_children = True
    for capture_node, capture_name in captures:
        if capture_node == node:
            should_traverse_children = False

    for capture_node, capture_index in captures:
        text = code[capture_node.start_byte : capture_node.end_byte].decode("utf-8").strip()

        if capture_index == "import":
            node_tree.imports.append(text)
        elif capture_index == "package":
            package_name_match = re.search(r'package\s+(\w+)', text)
            if package_name_match:
                node_tree.package = package_name_match.group(1)
        elif capture_index in ["function", "method"]:
            function_details = extract_function_details_go(text)
            if function_details and not any(f.name == function_details.name for f in node_tree.functions):
                node_tree.functions.append(function_details)
        elif capture_index == "type":
            type_name_match = re.search(r'type\s+(\w+)\s+struct', text)
            if type_name_match:
                node_tree.class_names.append(type_name_match.group(1))
        elif capture_index == "var":
            node_tree.property_declarations.append(text)

    if should_traverse_children:
        for child in node.children:
            traverse_tree_go(child, code, node_tree, language)

def extract_function_details_go(text):
    func_name_match = re.search(r'func\s+(\w+)\s*\(', text)
    if not func_name_match:  # Handle methods
        func_name_match = re.search(r'func\s*\(\s*\w+\s+\*\w+\s*\)\s+(\w+)\s*\(', text)
    func_name = func_name_match.group(1) if func_name_match else "anonymous"
    parameters_match = re.search(r'\((.*?)\)', text)
    parameters = parameters_match.group(1).strip() if parameters_match else ""
    func_body_match = re.search(r'\{(.*)\}', text, re.DOTALL)
    func_body = func_body_match.group(1).strip() if func_body_match else ""

    return FunctionNode(
        name=func_name,
        parameters=parameters.split(",") if parameters else [],
        return_type="undefined",  # Go functions might not declare return types explicitly in all cases
        body=func_body
    )

def extract_property_name(property_declaration):
    pattern = (
        r"\b(?:(?:public|private|protected)\s+)*(?:(?:static|final)\s+)*[a-zA-Z_]"
        r"\w*(?:<.*>)?(?:\[\])?\s+([a-zA-Z_]\w*)|(?:(?:val|var))\s+([a-zA-Z_]\w*)"
    )

    match = re.search(pattern, property_declaration)
    if match:
        java_prop_name = match.group(1)
        kotlin_prop_name = match.group(2)
        return java_prop_name or kotlin_prop_name

    return None



def traverse_tree_js(node, code, node_tree, language):
    js_function = None
    query_string = """
    (import_statement) @import
    (class_declaration) @class
    (function_declaration) @function
    (arrow_function) @arrow_function
    (method_definition) @method
    (variable_declarator) @variable
    (export_statement) @export
    """
    query = language.query(query_string)
    captures = query.captures(node)

    should_traverse_children = True
    for capture_node, capture_name in captures:
        if capture_node == node:
            should_traverse_children = False

    for capture_node, capture_index in captures:
        text = code[capture_node.start_byte : capture_node.end_byte].decode("utf-8").strip()

        if capture_index == "import":
            node_tree.imports.append(text)
        elif capture_index == "class":
            class_name_match = re.search(r'class\s+(\w+)', text)
            if class_name_match:
                node_tree.class_names.append(class_name_match.group(1))
        elif capture_index in ["function", "arrow_function", "method"]:
            function_details = extract_function_details_js(text)
            if function_details and not any(f.name == function_details.name for f in node_tree.functions):
                node_tree.functions.append(function_details)
        elif capture_index == "variable":
            node_tree.property_declarations.append(text)
        elif capture_index == "export":
            node_tree.exports.append(text)  # Assuming you might want to track exports similarly

    if should_traverse_children:
        for child in node.children:
            traverse_tree_js(child, code, node_tree, language)

def extract_function_details_js(text):
    func_name_match = re.search(r'function\s+(\w+)\s*\(', text)
    if not func_name_match:  # Check for arrow functions or anonymous functions
        func_name_match = re.search(r'(\w+)\s*=\s*\(', text)
    func_name = func_name_match.group(1) if func_name_match else "anonymous"
    parameters_match = re.search(r'\((.*?)\)', text)
    parameters = parameters_match.group(1).strip() if parameters_match else ""
    func_body_match = re.search(r'\{(.*)\}', text, re.DOTALL)
    func_body = func_body_match.group(1).strip() if func_body_match else ""

    return FunctionNode(
        name=func_name,
        parameters=parameters.split(",") if parameters else [],
        return_type="n/a",  # JavaScript functions do not explicitly declare return types
        body=func_body
    )



def traverse_tree_kt(node, code, node_tree, language):
    kotlin_function = None
    query_string = """
    (import_list) @import
    (package_header) @package
    (class_declaration) @class_or_interface
    (annotation) @annotation
    (object_declaration) @object_declaration
    (property_declaration) @field
    (function_declaration) @function
    """

    query = language.query(query_string)
    captures = query.captures(node)

    should_traverse_children = True
    for capture_node, capture_name in captures:
        if capture_node == node:
            should_traverse_children = False

    is_data_class = False
    for capture_node, capture_index in captures:
        if capture_index == "import":
            node_tree.imports = (
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            ).split("\n")

        elif capture_index == "package":
            node_tree.package = (
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            )

        elif capture_index == "class_or_interface":
            class_code = code[capture_node.start_byte : capture_node.end_byte].decode(
                "utf-8"
            )
            class_name_match = re.search(
                r"\b(?:sealed\s+class|data\s+class|class|interface)\s+([a-zA-Z_]\w*)",
                class_code,
            )
            if class_name_match:
                class_name = class_name_match.group(1)
                is_data_class = "data class" in class_code
                node_tree.class_names.append(f"{class_name}")
                node_tree.is_interface = "interface" in class_code

                # Extract data class fields
                if is_data_class:
                    # Modified regular expression to capture the entire line for each property
                    fields = re.findall(
                        r"\b(val|var)\s+([a-zA-Z_]\w*\s*:\s*[a-zA-Z_]\w*(\??)(<.*>)?(\??))",
                        class_code,
                    )
                    node_tree.property_declarations = (
                        ",\n".join(" ".join(f) for f in fields)
                    ).split("\n")

        elif capture_index == "annotation":
            annotation_text = (
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            )
            if kotlin_function:
                kotlin_function.annotations.append(annotation_text)

        # Added extraction of object declarations
        elif capture_index == "object_declaration":
            object_name_match = re.search(
                r"\b(?:object)\s+([a-zA-Z_]\w*)",
                code[capture_node.start_byte : capture_node.end_byte].decode("utf-8"),
            )
            if object_name_match:
                object_name = object_name_match.group(1)
                node_tree.class_names.append(object_name)

        elif capture_index == "field" and not is_data_class:
            property_declaration = (
                code[capture_node.start_byte : capture_node.end_byte]
                .decode("utf-8")
                .strip()
            )
            node_tree.property_declarations.append(property_declaration)

        elif capture_index == "function":
            function_code = code[
                capture_node.start_byte : capture_node.end_byte
            ].decode("utf-8")
            func_name_match = re.search(
                r"\b(?:fun)\s+(?:[a-zA-Z_]\w*\.)*([a-zA-Z_]\w*)", function_code
            )
            if func_name_match:
                func_name = func_name_match.group(1)
                parameters_match = re.search(r"\((.*?)\)", function_code)
                parameters = parameters_match.group(1) if parameters_match else ""
                return_type_match = re.search(
                    r":\s*([a-zA-Z_][\w<>,.? ]*)", function_code
                )
                return_type = (
                    return_type_match.group(1).strip() if return_type_match else "Unit"
                )
                func_body_match = re.search(r"\{(.*)\}", function_code, re.DOTALL)
                func_body = func_body_match.group(1).strip() if func_body_match else ""
                kotlin_function = FunctionNode(
                    func_name,
                    parameters.split(","),
                    return_type,
                    func_body,
                    class_names=node_tree.class_names,
                )

                # Check for duplicates
                duplicate_found = any(
                    func.name == kotlin_function.name
                    and func.return_type == kotlin_function.return_type
                    and func.parameters == kotlin_function.parameters
                    for func in node_tree.functions
                )
                if not duplicate_found:
                    node_tree.functions.append(kotlin_function)
    if should_traverse_children:
        for child in node.children:
            traverse_tree_kt(child, code, node_tree, language)
    else:
        # Append class names, function names, and property names to package_import_paths
        if node_tree.package:
            package_name = node_tree.package.replace(";", "").strip()
            if node_tree.class_names:
                for class_name in node_tree.class_names:
                    append_to_package_import_paths(package_name, class_name, node_tree)
            if node_tree.functions:
                for function in node_tree.functions:
                    append_to_package_import_paths(
                        package_name, function.name, node_tree
                    )
            if node_tree.property_declarations:
                for property_declaration in node_tree.property_declarations:
                    property_name = extract_property_name(property_declaration)
                    if property_name:
                        append_to_package_import_paths(
                            package_name, property_name, node_tree
                        )


def append_to_package_import_paths(package, name, node_tree):
    package_import_path = f"{package}.{name}".strip("package ")
    node_tree.package_import_paths[package_import_path] = package_import_path


def traverse_tree_python(node, code, node_tree, language):
    query_string = """
    (import_from_statement) @import_from
    (import_statement) @import
    (class_definition) @class
    (function_definition) @function
    (assignment) @variable
    """
    query = language.query(query_string)
    captures = query.captures(node)

    should_traverse_children = True
    for capture_node, capture_name in captures:
        if capture_node == node:
            should_traverse_children = False

    for capture_node, capture_index in captures:
        extracted_text = code[capture_node.start_byte : capture_node.end_byte].decode("utf-8").strip()

        if capture_index == "import":
            node_tree.imports.append(extracted_text)
        elif capture_index == "import_from":
            module_name = ' '.join([node.text.decode('utf-8') for node in capture_node.named_children if node.type == 'identifier'])
            import_name = capture_node.child_by_field_name('name').text.decode('utf-8')
            node_tree.imports.append(f"from {module_name} import {import_name}")
        elif capture_index == "class":
            class_name_match = re.search(r'class\s+(\w+)', extracted_text)
            if class_name_match:
                node_tree.class_names.append(class_name_match.group(1))
        elif capture_index == "function":
            function_details = extract_function_details_python(extracted_text)
            if function_details and not any(f.name == function_details.name for f in node_tree.functions):
                node_tree.functions.append(function_details)
        elif capture_index == "variable":
            if not node_tree.functions and not node_tree.class_names:
                node_tree.property_declarations.append(extracted_text)

    if should_traverse_children:
        for child in node.children:
            traverse_tree_python(child, code, node_tree, language)


def extract_function_details_python(text):
    func_name_match = re.search(r'def\s+(\w+)\s*\(', text)
    if func_name_match:
        func_name = func_name_match.group(1)
        parameters_match = re.search(r'\((.*?)\)', text)
        parameters = parameters_match.group(1).strip() if parameters_match else ""
        func_body_match = re.search(r':\s*\n(.*?)(^\s*$|\Z)', text, re.DOTALL | re.MULTILINE)
        func_body = func_body_match.group(1).strip() if func_body_match else ""

        return FunctionNode(
            name=func_name,
            parameters=parameters.split(",") if parameters else [],
            return_type="None",
            body=func_body
        )

    return None

def traverse_tree_swift(node, code, node_tree, language):
    query_string = """
    (import_declaration) @import
    (class_declaration) @class
    (function_declaration) @function
    (property_declaration) @variable
    """
    query = language.query(query_string)
    captures = query.captures(node)

    for capture_node, capture_name in captures:
        text = code[capture_node.start_byte : capture_node.end_byte].decode("utf-8").strip()

        if capture_name == "import":
            node_tree.imports.append(text)
        elif capture_name == "class":
            class_name_match = re.search(r'(class|struct|actor|extension|enum)\s+(\w+)', text)
            if class_name_match:
                node_tree.class_names.append(class_name_match.group(2))
        elif capture_name == "function":
            function_details = extract_function_details_swift(text)
            if function_details and not any(f.name == function_details.name for f in node_tree.functions):
                node_tree.functions.append(function_details)
        elif capture_name == "variable":
            node_tree.property_declarations.append(text)

    for child in node.children:
        traverse_tree_swift(child, code, node_tree, language)

def extract_function_details_swift(text):
    func_name_match = re.search(r'func\s+(\w+)\s*\(', text)
    func_name = func_name_match.group(1) if func_name_match else "anonymous"
    parameters_match = re.search(r'\((.*?)\)', text)
    parameters = parameters_match.group(1).strip() if parameters_match else ""
    return_type_match = re.search(r'->\s*(\w+)', text)
    return_type = return_type_match.group(1).strip() if return_type_match else "Void"
    func_body_match = re.search(r'\{(.*)\}', text, re.DOTALL)
    func_body = func_body_match.group(1).strip() if func_body_match else ""

    return FunctionNode(
        name=func_name,
        parameters=parameters.split(",") if parameters else [],
        return_type=return_type,
        body=func_body
    )




##### Model struture to hold parsed code #####

class TreeNode:
    def __init__(self, file_path=None, class_names=None, package_import_paths=None, package=None, imports=None, functions=None, property_declarations=None, exports=None):
        self.file_path = file_path
        self.class_names = class_names or []
        self.package_import_paths = package_import_paths or {}
        self.package = package
        self.imports = imports or []
        self.exports = exports or []
        self.property_declarations = property_declarations or []
        self.functions = functions or []

    def to_dict(self):
        return {
            "file_path": self.file_path,
            "class_names": self.class_names,
            "imports": self.imports,
            "exports": self.exports,
            "package_import_paths": self.package_import_paths,
            "package": self.package,
            "property_declarations": self.property_declarations,
            "functions": [func.to_dict() for func in self.functions]
        }

    def __repr__(self):
        functions = "\n\n".join([str(func) for func in self.functions])
        return (
            f"TreeNode:\nFile Path:{self.file_path}\nClass Names: {self.class_names}\n"
            f"Imports: {self.imports}\nExports: {self.exports}\nProperties: {self.property_declarations}\n"
            f"Functions:\n{functions}\nPackage Paths:{self.package_import_paths}\nPackage: {self.package}"
        )

class FunctionNode:
    def __init__(self, name, parameters, return_type, body, is_abstract=False, class_names=None, annotations=None):
        self.name = name
        self.parameters = parameters or []
        self.return_type = return_type
        self.body = body
        self.is_abstract = is_abstract
        self.class_name = " ".join(class_names) if class_names else ""
        self.annotations = annotations or []

    def to_dict(self):
        body = self.body.decode("utf-8") if isinstance(self.body, bytes) else self.body
        return {
            "name": self.name,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "body": body,
            "is_abstract": self.is_abstract,
            "class_name": self.class_name,
            "annotations": self.annotations,
        }

    def __repr__(self):
        parameter_str = ", ".join(self.parameters)
        return (
            f"\n\n------ Name: {self.name}\n------ Parameters: {parameter_str}\n------ Return Type: "
            f"{self.return_type}\n------ Body:\t{self.body}"
            f"\n------ Abstract:\t{self.is_abstract}\n"
            f"\n------ Annotations:\t{self.annotations}\n------ Class Name:\t{self.class_name}"
        )

    def to_json(self):
        if isinstance(self.body, bytes):
            self.body = self.body.decode("utf-8")
        return json.dumps(self.__dict__, indent=4)
