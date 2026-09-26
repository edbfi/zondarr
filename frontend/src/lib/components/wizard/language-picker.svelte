<script lang="ts">
/**
 * Language Picker Component
 *
 * Searchable dropdown for selecting a language from the full ISO 639-1 list.
 * Used in the step editor to add translation languages.
 */
import { Plus } from '@lucide/svelte';
import { slide } from 'svelte/transition';
import { Button } from '$lib/components/ui/button';

interface Props {
	languages: { code: string; label: string }[];
	onSelect: (code: string) => void;
}

const { languages, onSelect }: Props = $props();

let open = $state(false);
let search = $state('');
let wrapperRef = $state<HTMLDivElement | null>(null);
let searchInputRef = $state<HTMLInputElement | null>(null);

const filtered = $derived.by(() => {
	if (!search) return languages;
	const q = search.toLowerCase();
	return languages.filter(
		(l) => l.code.toLowerCase().includes(q) || l.label.toLowerCase().includes(q)
	);
});

function toggle() {
	open = !open;
	search = '';
	if (!open) return;
	// Focus search input after DOM update
	requestAnimationFrame(() => searchInputRef?.focus());
}

function select(code: string) {
	onSelect(code);
	open = false;
	search = '';
}

function handleKeydown(event: KeyboardEvent) {
	if (event.key === 'Escape') {
		open = false;
		search = '';
	}
}

function handleClickOutside(event: MouseEvent) {
	if (open && wrapperRef && !wrapperRef.contains(event.target as Node)) {
		open = false;
		search = '';
	}
}

$effect(() => {
	if (open) {
		document.addEventListener('click', handleClickOutside, true);
		return () => document.removeEventListener('click', handleClickOutside, true);
	}
});
</script>

<div class="language-picker-wrapper" bind:this={wrapperRef}>
	<Button
		variant="ghost"
		size="sm"
		onclick={toggle}
		class="text-cr-text-muted hover:text-cr-accent"
	>
		<Plus size={14} />
		Add Language
	</Button>

	{#if open}
		<div
			class="language-picker-dropdown"
			transition:slide={{ duration: 150 }}
			onkeydown={handleKeydown}
			role="listbox"
			tabindex="-1"
			aria-label="Select a language"
		>
			<div class="language-picker-search">
				<input
					bind:this={searchInputRef}
					bind:value={search}
					type="text"
					placeholder="Search languages..."
					class="language-picker-input"
					aria-label="Filter languages"
				>
			</div>
			<div class="language-picker-list">
				{#each filtered as lang (lang.code)}
					<button
						type="button"
						class="language-picker-option"
						role="option"
						aria-selected={false}
						onclick={() => select(lang.code)}
					>
						<span class="language-picker-code">{lang.code}</span>
						<span class="language-picker-name">{lang.label}</span>
					</button>
				{:else}
					<p class="language-picker-empty">No languages found</p>
				{/each}
			</div>
		</div>
	{/if}
</div>

<style>
.language-picker-wrapper {
	position: relative;
}

.language-picker-dropdown {
	position: absolute;
	top: 100%;
	left: 0;
	z-index: 10;
	margin-top: 0.25rem;
	min-width: 16rem;
	background: var(--cr-surface);
	border: 1px solid var(--cr-border);
	border-radius: 0.5rem;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
	overflow: hidden;
}

.language-picker-search {
	padding: 0.5rem;
	border-bottom: 1px solid var(--cr-border);
}

.language-picker-input {
	width: 100%;
	padding: 0.375rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--cr-text);
	background: var(--cr-bg);
	border: 1px solid var(--cr-border);
	border-radius: 0.375rem;
	outline: none;
	transition: border-color 0.15s ease;
}

.language-picker-input:focus {
	border-color: var(--cr-accent);
}

.language-picker-input::placeholder {
	color: var(--cr-text-muted);
}

.language-picker-list {
	max-height: 300px;
	overflow-y: auto;
	padding: 0.25rem;
}

.language-picker-option {
	display: flex;
	align-items: center;
	gap: 0.5rem;
	width: 100%;
	padding: 0.5rem 0.625rem;
	font-size: 0.8125rem;
	color: var(--cr-text);
	background: transparent;
	border: none;
	border-radius: 0.375rem;
	cursor: pointer;
	text-align: left;
	transition: background 0.1s ease;
}

.language-picker-option:hover {
	background: var(--cr-accent-highlight);
	color: var(--cr-accent);
}

.language-picker-code {
	font-size: 0.6875rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--cr-text-muted);
	min-width: 1.75rem;
}

.language-picker-option:hover .language-picker-code {
	color: var(--cr-accent);
}

.language-picker-name {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.language-picker-empty {
	padding: 0.75rem 0.625rem;
	font-size: 0.75rem;
	color: var(--cr-text-muted);
	text-align: center;
	margin: 0;
}
</style>
