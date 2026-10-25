import * as monaco from 'monaco-editor/editor/editor.api.js'
import EditorWorker from 'monaco-editor/editor/editor.worker.js?worker'
import TypeScriptWorker from 'monaco-editor/language/typescript/ts.worker.js?worker'
import { javascriptDefaults, typescriptDefaults, ScriptTarget } from 'monaco-editor/languages/features/typescript/register.js'
import 'monaco-editor/editor/browser/coreCommands.js'
import 'monaco-editor/editor/contrib/bracketMatching/browser/bracketMatching.js'
import 'monaco-editor/editor/contrib/clipboard/browser/clipboard.js'
import 'monaco-editor/editor/contrib/comment/browser/comment.js'
import 'monaco-editor/editor/contrib/contextmenu/browser/contextmenu.js'
import 'monaco-editor/editor/contrib/find/browser/findController.js'
import 'monaco-editor/editor/contrib/folding/browser/folding.js'
import 'monaco-editor/editor/contrib/hover/browser/hoverContribution.js'
import 'monaco-editor/editor/contrib/indentation/browser/indentation.js'
import 'monaco-editor/editor/contrib/linesOperations/browser/linesOperations.js'
import 'monaco-editor/editor/contrib/parameterHints/browser/parameterHints.js'
import 'monaco-editor/editor/contrib/snippet/browser/snippetController2.js'
import 'monaco-editor/editor/contrib/suggest/browser/suggestController.js'
import 'monaco-editor/editor/contrib/wordOperations/browser/wordOperations.js'
import 'monaco-editor/languages/definitions/python/register.js'
import 'monaco-editor/languages/definitions/javascript/register.js'
import 'monaco-editor/languages/definitions/typescript/register.js'
import 'monaco-editor/languages/definitions/java/register.js'
import 'monaco-editor/languages/definitions/cpp/register.js'
import 'monaco-editor/languages/definitions/go/register.js'
import 'monaco-editor/languages/definitions/rust/register.js'
import 'monaco-editor/languages/definitions/sql/register.js'

// Worker 随应用打包，不依赖 CDN，也不把代码发往外部服务。
globalThis.MonacoEnvironment = {
  getWorker(_id: string, label: string) {
    return label === 'typescript' || label === 'javascript' ? new TypeScriptWorker() : new EditorWorker()
  },
}

for (const defaults of [javascriptDefaults, typescriptDefaults]) {
  defaults.setCompilerOptions({ target: ScriptTarget.ESNext, allowNonTsExtensions: true, allowJs: true })
  // 手撕片段可能没有入口或外部类型，仍保留语法检查与补全。
  defaults.setDiagnosticsOptions({ noSemanticValidation: true, noSyntaxValidation: false })
}

export const codingLanguages = ['Python', 'Java', 'C++', 'C', 'JavaScript', 'TypeScript', 'Go', 'Rust', 'SQL']
const languageIds: Record<string, string> = {
  python: 'python', py: 'python', java: 'java', 'c++': 'cpp', cpp: 'cpp', c: 'c',
  javascript: 'javascript', js: 'javascript', typescript: 'typescript', ts: 'typescript',
  go: 'go', golang: 'go', rust: 'rust', sql: 'sql',
}
export const editorLanguage = (label: string) => languageIds[label.trim().toLowerCase()] ?? 'plaintext'

type Snippet = { label: string; body: string; detail: string }
const snippets: Record<string, Snippet[]> = {
  python: [
    { label: 'def', body: 'def ${1:solve}(${2:args}):\n    ${0:pass}', detail: '函数定义' },
    { label: 'for', body: 'for ${1:item} in ${2:items}:\n    $0', detail: '遍历序列' },
    { label: 'enumerate', body: 'for ${1:i}, ${2:value} in enumerate(${3:nums}):\n    $0', detail: '遍历下标和值' },
    { label: 'if', body: 'if ${1:condition}:\n    $0', detail: '条件分支' },
    { label: 'class', body: 'class ${1:Solution}:\n    def ${2:solve}(self, ${3:nums}):\n        $0', detail: '题解类' },
  ],
  javascript: [
    { label: 'function', body: 'function ${1:solve}(${2:args}) {\n    $0\n}', detail: '函数定义' },
    { label: 'forof', body: 'for (const ${1:value} of ${2:items}) {\n    $0\n}', detail: '遍历序列' },
  ],
  typescript: [{ label: 'function', body: 'function ${1:solve}(${2:nums}: ${3:number[]}): ${4:number} {\n    $0\n}', detail: '带类型的函数' }],
  java: [
    { label: 'solution', body: 'class Solution {\n    public ${1:int} ${2:solve}(${3:int[] nums}) {\n        $0\n    }\n}', detail: '题解类' },
    { label: 'for', body: 'for (int ${1:i} = 0; ${1:i} < ${2:n}; ${1:i}++) {\n    $0\n}', detail: '下标循环' },
  ],
  cpp: [
    { label: 'solution', body: 'class Solution {\npublic:\n    ${1:int} ${2:solve}(${3:vector<int>& nums}) {\n        $0\n    }\n};', detail: '题解类' },
    { label: 'for', body: 'for (int ${1:i} = 0; ${1:i} < ${2:n}; ++${1:i}) {\n    $0\n}', detail: '下标循环' },
  ],
  c: [{ label: 'for', body: 'for (int ${1:i} = 0; ${1:i} < ${2:n}; ++${1:i}) {\n    $0\n}', detail: '下标循环' }],
  go: [{ label: 'func', body: 'func ${1:solve}(${2:nums []int}) ${3:int} {\n    $0\n}', detail: '函数定义' }],
  rust: [{ label: 'fn', body: 'fn ${1:solve}(${2:nums: Vec<i32>}) -> ${3:i32} {\n    $0\n}', detail: '函数定义' }],
  sql: [{ label: 'select', body: 'SELECT ${1:*}\nFROM ${2:table_name}\nWHERE ${0:condition};', detail: '查询语句' }],
}

const pythonBuiltins = 'abs all any bool dict enumerate filter float int isinstance len list map max min range reversed set sorted str sum tuple zip print'.split(' ')
const keywords: Record<string, string[]> = {
  python: 'and as assert async await break continue elif else except False finally from global import in is lambda None nonlocal not or pass raise return True try while with yield'.split(' '),
  java: 'abstract boolean break case catch char continue double else extends final finally if implements import instanceof int interface long new null private protected public return static String super switch this throw throws true try void while'.split(' '),
  cpp: 'auto bool break case catch char const continue double else false float if int long namespace new nullptr private protected public return sizeof static std string struct switch template this throw true try typename using vector virtual void while'.split(' '),
  c: 'break case char const continue default do double else enum float if int long return short signed sizeof static struct switch typedef union unsigned void volatile while'.split(' '),
  go: 'append break case chan const continue defer else error false go if import interface len make map nil package range return select struct switch true type var'.split(' '),
  rust: 'as async await break const continue else enum false impl let loop match mod move mut None Ok Option pub ref return self Some static String struct super trait true use Vec where while'.split(' '),
  sql: 'SELECT FROM WHERE JOIN LEFT RIGHT INNER ON GROUP BY ORDER ASC DESC HAVING LIMIT DISTINCT COUNT SUM AVG MAX MIN AS AND OR NOT NULL IN EXISTS UNION'.split(' '),
}

// 非 JS/TS 语言提供关键词、常用内置函数、可跳转占位符的片段和文档内词补全。
for (const language of new Set([...Object.keys(snippets), ...Object.keys(keywords)])) {
  monaco.languages.registerCompletionItemProvider(language, {
    provideCompletionItems(model, position) {
      const word = model.getWordUntilPosition(position)
      const range = new monaco.Range(position.lineNumber, word.startColumn, position.lineNumber, word.endColumn)
      return { suggestions: [
        ...(snippets[language] ?? []).map(snippet => ({
          label: snippet.label, detail: snippet.detail, kind: monaco.languages.CompletionItemKind.Snippet,
          insertText: snippet.body, insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
          range, sortText: `0_${snippet.label}`,
        })),
        ...(keywords[language] ?? []).map(label => ({ label, kind: monaco.languages.CompletionItemKind.Keyword, insertText: label, range })),
        ...(language === 'python' ? pythonBuiltins.map(label => ({ label, detail: 'Python 内置函数',
          kind: monaco.languages.CompletionItemKind.Function, insertText: `${label}(\${1})`,
          insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range })) : []),
      ] }
    },
  })
}

monaco.editor.defineTheme('coding-night', {
  base: 'vs-dark', inherit: true,
  rules: [
    { token: 'comment', foreground: '8B93AA', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'C4AEF7' }, { token: 'string', foreground: 'A6D5B1' },
    { token: 'number', foreground: 'E6BB8D' }, { token: 'type', foreground: '88CEE0' },
  ],
  colors: {
    'editor.background': '#222537', 'editor.foreground': '#E8EAF4',
    'editorLineNumber.foreground': '#7F88A5', 'editorLineNumber.activeForeground': '#D9DCF0',
    'editor.lineHighlightBackground': '#2B2F45', 'editor.selectionBackground': '#514A7F',
    'editorCursor.foreground': '#C4AEF7', 'editorIndentGuide.background1': '#353B53',
    'editorWidget.background': '#2B2F45', 'editorWidget.border': '#454C69',
    'editorSuggestWidget.selectedBackground': '#4A426E',
  },
})

export { monaco }
