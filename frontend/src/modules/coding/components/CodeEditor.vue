<template>
  <div class="code-editor-shell">
    <div ref="host" class="editor-host" />
    <div class="editor-status" aria-live="off">
      <span>{{ language }} · {{ wrapped ? '自动换行' : '4 空格缩进' }}</span>
      <span>第 {{ cursor.lineNumber }} 行，第 {{ cursor.column }} 列</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { editorLanguage, monaco } from '../editor'

const props = defineProps<{ modelValue: string; language: string; readonly?: boolean; wrapped?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const host = ref<HTMLElement>()
const cursor = ref({ lineNumber: 1, column: 1 })
let editor: monaco.editor.IStandaloneCodeEditor | undefined
let model: monaco.editor.ITextModel | undefined
const disposables: monaco.IDisposable[] = []
let applying = false

onMounted(() => {
  if (!host.value) return
  model = monaco.editor.createModel(props.modelValue, editorLanguage(props.language))
  model.updateOptions({ tabSize: 4, insertSpaces: true })
  editor = monaco.editor.create(host.value, {
    model, theme: 'coding-night', automaticLayout: true, readOnly: props.readonly,
    ariaLabel: '代码编辑器', fontFamily: "Consolas, 'Cascadia Code', 'Courier New', monospace",
    fontSize: 14, lineHeight: 24, padding: { top: 18, bottom: 18 },
    minimap: { enabled: false }, lineNumbersMinChars: 3, scrollBeyondLastLine: false,
    wordWrap: props.wrapped ? 'on' : 'off', tabSize: 4, insertSpaces: true, detectIndentation: false,
    quickSuggestions: { other: true, comments: false, strings: false },
    wordBasedSuggestions: 'currentDocument', snippetSuggestions: 'top', tabCompletion: 'on',
    suggestOnTriggerCharacters: true, acceptSuggestionOnEnter: 'smart',
    autoIndent: 'full', autoClosingBrackets: 'always', autoClosingQuotes: 'always',
    bracketPairColorization: { enabled: true }, fixedOverflowWidgets: true,
    renderLineHighlight: 'line', renderWhitespace: 'selection', overviewRulerLanes: 0,
  })
  disposables.push(editor.onDidChangeModelContent(() => {
    if (!applying && model) emit('update:modelValue', model.getValue())
  }), editor.onDidChangeCursorPosition(event => { cursor.value = event.position }))
})

watch(() => props.modelValue, value => {
  if (!model || model.getValue() === value) return
  // 自动保存不重建 model，保留光标和撤销记录；加载不同内容时才替换。
  applying = true
  model.setValue(value)
  applying = false
})
watch(() => props.language, language => {
  if (model) monaco.editor.setModelLanguage(model, editorLanguage(language))
})
watch(() => props.readonly, readOnly => editor?.updateOptions({ readOnly }))
watch(() => props.wrapped, wrapped => editor?.updateOptions({ wordWrap: wrapped ? 'on' : 'off' }))

function complete() { editor?.focus(); void editor?.getAction('editor.action.triggerSuggest')?.run() }
function focus() { editor?.focus() }
defineExpose({ complete, focus })
onBeforeUnmount(() => {
  disposables.forEach(disposable => disposable.dispose())
  editor?.dispose()
  model?.dispose()
})
</script>

<style scoped>
.code-editor-shell { display: flex; flex-direction: column; min-width: 0; height: 100%; background: #222537; }
.editor-host { flex: 1; min-height: 360px; min-width: 0; overflow: hidden; }
.editor-status { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; padding: 8px 16px; border-top: 1px solid #353b53; color: #b0b7cd; font: 11px/1.5 Consolas, 'Microsoft YaHei', monospace; }
</style>
