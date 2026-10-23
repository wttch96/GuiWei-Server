<script setup>
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ gfm: true, breaks: true })

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

const props = defineProps({
  content: { type: String, default: '' },
})

const html = computed(() => DOMPurify.sanitize(marked.parse(props.content || '')))
</script>

<template>
  <div class="markdown-body" v-html="html" />
</template>

<style scoped>
.markdown-body {
  font-size: 13.5px;
  line-height: 1.75;
  white-space: normal;
  word-break: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 14px 0 6px;
  line-height: 1.45;
  font-weight: 650;
  color: var(--ink);
}

.markdown-body :deep(h1) {
  font-size: 17px;
}

.markdown-body :deep(h2) {
  font-size: 15.5px;
}

.markdown-body :deep(h3) {
  font-size: 14.5px;
}

.markdown-body :deep(h4) {
  font-size: 13.5px;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 4px 0 8px;
  padding-left: 21px;
}

.markdown-body :deep(li) {
  margin: 2px 0;
}

.markdown-body :deep(li > p) {
  margin: 0;
}

.markdown-body :deep(strong) {
  font-weight: 650;
  color: var(--brand-deep);
}

.markdown-body :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: #e9f2ef;
  color: #245c50;
  font-family: 'JetBrains Mono', 'Cascadia Code', Consolas, monospace;
  font-size: 12px;
}

.markdown-body :deep(pre) {
  margin: 8px 0;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #eef4f1;
  overflow-x: auto;
}

.markdown-body :deep(pre code) {
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 12px;
  line-height: 1.6;
}

.markdown-body :deep(blockquote) {
  margin: 8px 0;
  padding: 2px 0 2px 12px;
  border-left: 3px solid var(--brand-line);
  color: var(--ink-2);
}

.markdown-body :deep(table) {
  display: block;
  max-width: 100%;
  margin: 8px 0;
  border-collapse: collapse;
  overflow-x: auto;
  font-size: 12.5px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 6px 10px;
  border: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}

.markdown-body :deep(th) {
  background: #eef4f1;
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: var(--brand-deep);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.markdown-body :deep(hr) {
  margin: 12px 0;
  border: none;
  border-top: 1px solid var(--line);
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 8px;
}

.markdown-body :deep(> :first-child) {
  margin-top: 0;
}

.markdown-body :deep(> :last-child) {
  margin-bottom: 0;
}
</style>
