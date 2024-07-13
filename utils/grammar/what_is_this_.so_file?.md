# wut in the tree sitter (o.O')

## 1. what it it??
    The languages.so file is a shared object library that contains compiled tree-sitter grammars for various programming languages. Tree-sitter is a parser generator tool and an incremental parsing library that can build a concrete syntax tree for source files in different programming languages.

## 2. hows it built?

    Use the `/grammar_utils/language_grammar_builder.py` to clone and build the list of repositories containing the Tree-sitter grammars is defined in a file called `language_grammar_repos.txt`-- if they haven't been cloned already.

    *** SUPPORT MISSING LANGUAGES BY ADDING TO `language_grammar_repos.txt` ***

    the code: `tree_sitter.Language.build_library` is what actually compiles the grammars from the cloned repositories into a shared object file (languages.so or languages.dll on Windows).


## 3. hows it used:
   The code uses the languages.so file through the Language class from the tree_sitter module.
   Here's the relevant line:

    ```python

      LANGUAGE_SO_PATH = "./grammar_utils/language_grammars.so"

      LANGUAGE_DATA = {
          "java": ("java", [".java"]),
          ....
          "YOUR_FAV_LANGUAGE_HERE": ("<lang>", ["<lang.extension>"])
      }

      def create_language(name):
          return Language(LANGUAGE_SO_PATH, name)

      def init_tree_sitter_languages():
          global extension_to_language
          extension_to_language = {
              lang: (create_language(data[0]), data[1])
              for lang, data in LANGUAGE_DATA.items()
          }
    ```
   These language objects are then used to initialize parsers for each supported language.

## 4. the parsers an action

    See, & Run [or Modify] `unit_test/tree_sitter_test.py` to get started.


Happy Parsin'
