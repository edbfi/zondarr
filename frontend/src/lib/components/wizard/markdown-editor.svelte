<script lang="ts">
/**
 * Markdown Editor Component
 *
 * Implements textarea with markdown input, formatting toolbar, and live preview
 * with sanitized HTML.
 *
 * @module $lib/components/wizard/markdown-editor
 */

import { renderMarkdown } from './markdown-utils';

interface Props {
	value: string;
	placeholder?: string;
	rows?: number;
}

let {
	value = $bindable(''),
	placeholder = 'Enter markdown content...',
	rows = 8
}: Props = $props();

// Tab state for switching between edit and preview
let activeTab = $state<'edit' | 'preview'>('edit');
let textareaRef = $state<HTMLTextAreaElement | null>(null);

// Render markdown with sanitization
const renderedHtml = $derived.by(() => {
	if (!value) return '<p class="empty-preview">Preview will appear here...</p>';
	return renderMarkdown(value);
});

/**
 * Insert markdown formatting around the current selection or at cursor.
 */
function insertFormatting(before: string, after: string, defaultText: string) {
	if (!textareaRef) return;

	const start = textareaRef.selectionStart;
	const end = textareaRef.selectionEnd;
	const selected = value.slice(start, end);
	const text = selected || defaultText;

	const newValue = value.slice(0, start) + before + text + after + value.slice(end);
	value = newValue;

	// Restore cursor position after the inserted text
	requestAnimationFrame(() => {
		if (!textareaRef) return;
		textareaRef.focus();
		if (selected) {
			// If text was selected, select the formatted text
			textareaRef.selectionStart = start + before.length;
			textareaRef.selectionEnd = start + before.length + text.length;
		} else {
			// If no selection, select the default text for easy replacement
			textareaRef.selectionStart = start + before.length;
			textareaRef.selectionEnd = start + before.length + defaultText.length;
		}
	});
}

/**
 * Insert a line-level formatting (heading, list item, blockquote).
 */
function insertLineFormatting(prefix: string, defaultText: string) {
	if (!textareaRef) return;

	const start = textareaRef.selectionStart;
	const end = textareaRef.selectionEnd;
	const selected = value.slice(start, end);
	const text = selected || defaultText;

	// Find the start of the current line
	const lineStart = value.lastIndexOf('\n', start - 1) + 1;
	const beforeLine = value.slice(0, lineStart);
	const afterCursor = value.slice(end);

	// Check if we need a newline before the prefix
	const needsNewline = lineStart > 0 && value[lineStart - 1] !== '\n';

	const newValue = beforeLine + (needsNewline ? '\n' : '') + prefix + text + afterCursor;
	value = newValue;

	const offset = (needsNewline ? 1 : 0) + prefix.length;
	requestAnimationFrame(() => {
		if (!textareaRef) return;
		textareaRef.focus();
		if (selected) {
			textareaRef.selectionStart = lineStart + offset;
			textareaRef.selectionEnd = lineStart + offset + text.length;
		} else {
			textareaRef.selectionStart = lineStart + offset;
			textareaRef.selectionEnd = lineStart + offset + defaultText.length;
		}
	});
}

function formatBold() {
	insertFormatting('**', '**', 'bold text');
}

function formatItalic() {
	insertFormatting('*', '*', 'italic text');
}

function formatHeading() {
	insertLineFormatting('## ', 'Heading');
}

function formatLink() {
	if (!textareaRef) return;

	const start = textareaRef.selectionStart;
	const end = textareaRef.selectionEnd;
	const selected = value.slice(start, end);

	if (selected) {
		// Wrap selected text as link text
		const newValue = `${value.slice(0, start)}[${selected}](url)${value.slice(end)}`;
		value = newValue;
		requestAnimationFrame(() => {
			if (!textareaRef) return;
			textareaRef.focus();
			// Select "url" for easy replacement
			textareaRef.selectionStart = start + selected.length + 3;
			textareaRef.selectionEnd = start + selected.length + 6;
		});
	} else {
		insertFormatting('[', '](url)', 'link text');
	}
}

function formatImage() {
	if (!textareaRef) return;

	const start = textareaRef.selectionStart;
	const end = textareaRef.selectionEnd;
	const selected = value.slice(start, end);

	if (selected) {
		// Use selected text as alt text
		const newValue = `${value.slice(0, start)}![${selected}](image-url)${value.slice(end)}`;
		value = newValue;
		requestAnimationFrame(() => {
			if (!textareaRef) return;
			textareaRef.focus();
			// Select "image-url" for easy replacement
			textareaRef.selectionStart = start + selected.length + 4;
			textareaRef.selectionEnd = start + selected.length + 13;
		});
	} else {
		insertFormatting('![', '](image-url)', 'alt text');
	}
}

function formatBulletList() {
	insertLineFormatting('- ', 'list item');
}

function formatNumberedList() {
	insertLineFormatting('1. ', 'list item');
}

function formatBlockquote() {
	insertLineFormatting('> ', 'quote');
}

function formatCode() {
	insertFormatting('`', '`', 'code');
}
</script>

<div class="markdown-editor">
	<!-- Tab buttons -->
	<div class="tabs">
		<button
			type="button"
			class="tab"
			class:active={activeTab === 'edit'}
			onclick={() => (activeTab = 'edit')}
		>
			Edit
		</button>
		<button
			type="button"
			class="tab"
			class:active={activeTab === 'preview'}
			onclick={() => (activeTab = 'preview')}
		>
			Preview
		</button>
	</div>

	<!-- Content area -->
	<div class="content">
		{#if activeTab === 'edit'}
			<!-- Formatting toolbar -->
			<div class="toolbar" role="toolbar" aria-label="Formatting options">
				<button type="button" class="toolbar-btn" onclick={formatBold} title="Bold (Ctrl+B)">
					<strong>B</strong>
				</button>
				<button type="button" class="toolbar-btn" onclick={formatItalic} title="Italic (Ctrl+I)">
					<em>I</em>
				</button>
				<button type="button" class="toolbar-btn" onclick={formatHeading} title="Heading">H</button>
				<div class="toolbar-divider"></div>
				<button type="button" class="toolbar-btn" onclick={formatLink} title="Link">
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
						<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
					</svg>
				</button>
				<button type="button" class="toolbar-btn" onclick={formatImage} title="Image">
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<rect width="18" height="18" x="3" y="3" rx="2" ry="2" />
						<circle cx="9" cy="9" r="2" />
						<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21" />
					</svg>
				</button>
				<button type="button" class="toolbar-btn" onclick={formatBulletList} title="Bullet list">
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<line x1="8" y1="6" x2="21" y2="6" />
						<line x1="8" y1="12" x2="21" y2="12" />
						<line x1="8" y1="18" x2="21" y2="18" />
						<line x1="3" y1="6" x2="3.01" y2="6" />
						<line x1="3" y1="12" x2="3.01" y2="12" />
						<line x1="3" y1="18" x2="3.01" y2="18" />
					</svg>
				</button>
				<button
					type="button"
					class="toolbar-btn"
					onclick={formatNumberedList}
					title="Numbered list"
				>
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<line x1="10" y1="6" x2="21" y2="6" />
						<line x1="10" y1="12" x2="21" y2="12" />
						<line x1="10" y1="18" x2="21" y2="18" />
						<path d="M4 6h1v4" />
						<path d="M4 10h2" />
						<path d="M6 18H4c0-1 2-2 2-3s-1-1.5-2-1" />
					</svg>
				</button>
				<div class="toolbar-divider"></div>
				<button type="button" class="toolbar-btn" onclick={formatBlockquote} title="Blockquote">
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<path
							d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21z"
						/>
						<path
							d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-2.75 4v3z"
						/>
					</svg>
				</button>
				<button type="button" class="toolbar-btn" onclick={formatCode} title="Inline code">
					<svg
						width="16"
						height="16"
						viewBox="0 0 24 24"
						fill="none"
						stroke="currentColor"
						stroke-width="2"
						stroke-linecap="round"
						stroke-linejoin="round"
						aria-hidden="true"
					>
						<polyline points="16 18 22 12 16 6" />
						<polyline points="8 6 2 12 8 18" />
					</svg>
				</button>
			</div>

			<textarea
				bind:this={textareaRef}
				bind:value
				{placeholder}
				{rows}
				class="editor-textarea"
				spellcheck="true"
			></textarea>
		{:else}
			<div class="preview prose prose-invert">
				{@html renderedHtml}
			</div>
		{/if}
	</div>
</div>

<style>
.markdown-editor {
	display: flex;
	flex-direction: column;
	border: 1px solid var(--cr-border);
	border-radius: 0.5rem;
	overflow: hidden;
	background: var(--cr-bg);
}

/* Tabs */
.tabs {
	display: flex;
	border-bottom: 1px solid var(--cr-border);
	background: var(--cr-surface);
}

.tab {
	flex: 1;
	padding: 0.625rem 1rem;
	font-size: 0.875rem;
	font-weight: 500;
	color: var(--cr-text-muted);
	background: transparent;
	border: none;
	cursor: pointer;
	transition: all 0.2s ease;
}

.tab:hover {
	color: var(--cr-text);
	background: hsl(220 15% 12%);
}

.tab.active {
	color: var(--cr-accent);
	background: var(--cr-bg);
	box-shadow: inset 0 -2px 0 var(--cr-accent);
}

/* Content area */
.content {
	min-height: 200px;
}

/* Formatting toolbar */
.toolbar {
	display: flex;
	align-items: center;
	gap: 0.125rem;
	padding: 0.375rem 0.5rem;
	border-bottom: 1px solid var(--cr-border);
	background: var(--cr-surface);
}

.toolbar-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 1.75rem;
	height: 1.75rem;
	padding: 0;
	font-size: 0.8125rem;
	font-family: inherit;
	color: var(--cr-text-muted);
	background: transparent;
	border: 1px solid transparent;
	border-radius: 0.25rem;
	cursor: pointer;
	transition: all 0.15s ease;
}

.toolbar-btn:hover {
	color: var(--cr-text);
	background: hsl(220 15% 15%);
	border-color: var(--cr-border);
}

.toolbar-btn:active {
	background: hsl(220 15% 12%);
}

.toolbar-divider {
	width: 1px;
	height: 1.25rem;
	margin: 0 0.25rem;
	background: var(--cr-border);
}

/* Editor textarea */
.editor-textarea {
	width: 100%;
	min-height: 200px;
	padding: 1rem;
	font-family: "JetBrains Mono", "Fira Code", monospace;
	font-size: 0.875rem;
	line-height: 1.6;
	color: var(--cr-text);
	background: transparent;
	border: none;
	resize: vertical;
	outline: none;
}

.editor-textarea::placeholder {
	color: var(--cr-text-muted);
}

/* Preview area */
.preview {
	padding: 1rem;
	min-height: 200px;
	font-size: 0.9375rem;
	line-height: 1.7;
	color: var(--cr-text-muted);
}

.preview :global(.empty-preview) {
	color: var(--cr-text-muted);
	font-style: italic;
}

/* Prose styles for preview */
.preview :global(h1),
.preview :global(h2),
.preview :global(h3),
.preview :global(h4),
.preview :global(h5),
.preview :global(h6) {
	color: var(--cr-text);
	font-weight: 600;
	margin-top: 1.5em;
	margin-bottom: 0.5em;
}

.preview :global(h1) {
	font-size: 1.5rem;
}

.preview :global(h2) {
	font-size: 1.25rem;
}

.preview :global(h3) {
	font-size: 1.125rem;
}

.preview :global(p) {
	margin-bottom: 1em;
}

.preview :global(a) {
	color: var(--cr-accent);
	text-decoration: underline;
	text-underline-offset: 2px;
}

.preview :global(a:hover) {
	opacity: 0.8;
}

.preview :global(strong) {
	color: var(--cr-text);
	font-weight: 600;
}

.preview :global(em) {
	font-style: italic;
}

.preview :global(ul),
.preview :global(ol) {
	margin-bottom: 1em;
	padding-left: 1.5em;
}

.preview :global(li) {
	margin-bottom: 0.25em;
}

.preview :global(blockquote) {
	margin: 1em 0;
	padding-left: 1em;
	border-left: 3px solid var(--cr-accent);
	color: var(--cr-text-muted);
	font-style: italic;
}

.preview :global(code) {
	font-family: "JetBrains Mono", "Fira Code", monospace;
	font-size: 0.875em;
	padding: 0.125rem 0.375rem;
	background: hsl(220 15% 12%);
	border-radius: 0.25rem;
}

.preview :global(pre) {
	margin: 1em 0;
	padding: 1rem;
	background: hsl(220 15% 10%);
	border-radius: 0.5rem;
	overflow-x: auto;
}

.preview :global(pre code) {
	padding: 0;
	background: transparent;
}
</style>
