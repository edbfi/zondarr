<script lang="ts">
/**
 * Language Switcher Component
 *
 * Compact dropdown for switching between available translations in wizard steps.
 * Only renders when there are multiple languages available.
 */

interface Props {
	languages: { code: string; label: string }[];
	selected: string;
	onSelect: (code: string) => void;
}

const { languages, selected, onSelect }: Props = $props();

let open = $state(false);
let buttonRef = $state<HTMLButtonElement | null>(null);
let menuRef = $state<HTMLDivElement | null>(null);

const selectedLabel = $derived(
	languages.find((l) => l.code === selected)?.label ?? selected.toUpperCase()
);

function toggle() {
	open = !open;
}

function select(code: string) {
	onSelect(code);
	open = false;
	buttonRef?.focus();
}

function handleKeydown(event: KeyboardEvent) {
	if (event.key === 'Escape') {
		open = false;
		buttonRef?.focus();
	}
	if (event.key === 'ArrowDown' && open && menuRef) {
		event.preventDefault();
		const first = menuRef.querySelector<HTMLButtonElement>('button');
		first?.focus();
	}
}

function handleMenuKeydown(event: KeyboardEvent) {
	const items = Array.from(menuRef?.querySelectorAll<HTMLButtonElement>('button') ?? []);
	const current = items.indexOf(document.activeElement as HTMLButtonElement);

	if (event.key === 'ArrowDown') {
		event.preventDefault();
		items[(current + 1) % items.length]?.focus();
	} else if (event.key === 'ArrowUp') {
		event.preventDefault();
		items[(current - 1 + items.length) % items.length]?.focus();
	} else if (event.key === 'Escape') {
		open = false;
		buttonRef?.focus();
	}
}

function handleClickOutside(event: MouseEvent) {
	if (
		open &&
		buttonRef &&
		menuRef &&
		!buttonRef.contains(event.target as Node) &&
		!menuRef.contains(event.target as Node)
	) {
		open = false;
	}
}

$effect(() => {
	if (open) {
		document.addEventListener('click', handleClickOutside, true);
		return () => document.removeEventListener('click', handleClickOutside, true);
	}
});
</script>

{#if languages.length > 1}
	<!-- biome-ignore lint/a11y/useSemanticElements: This ARIA group labels existing controls without introducing native fieldset layout. -->
	<div class="lang-switcher" role="group" aria-label="Language selection">
		<button
			type="button"
			bind:this={buttonRef}
			class="lang-trigger"
			aria-haspopup="listbox"
			aria-expanded={open}
			aria-label="Change language, currently {selectedLabel}"
			onclick={toggle}
			onkeydown={handleKeydown}
		>
			<svg class="lang-icon" viewBox="0 0 20 20" fill="none" aria-hidden="true">
				<circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="1.5" />
				<path
					d="M2.5 10h15M10 2.5c-2 2.5-2 5-2 7.5s0 5 2 7.5M10 2.5c2 2.5 2 5 2 7.5s0 5-2 7.5"
					stroke="currentColor"
					stroke-width="1.2"
				/>
			</svg>
			<span class="lang-code">{selectedLabel}</span>
			<svg class="lang-chevron" class:open viewBox="0 0 12 12" fill="none" aria-hidden="true">
				<path
					d="M3 5l3 3 3-3"
					stroke="currentColor"
					stroke-width="1.5"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
		</button>

		{#if open}
			<div
				bind:this={menuRef}
				class="lang-menu"
				role="listbox"
				tabindex="-1"
				aria-label="Available languages"
				onkeydown={handleMenuKeydown}
			>
				{#each languages as lang (lang.code)}
					<button
						type="button"
						class="lang-option"
						class:active={lang.code === selected}
						role="option"
						aria-selected={lang.code === selected}
						onclick={() => select(lang.code)}
					>
						{lang.label}
					</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}

<style>
.lang-switcher {
	position: relative;
	display: inline-flex;
	z-index: 10;
}

.lang-trigger {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	padding: 0.375rem 0.625rem;
	background: hsl(220 15% 10% / 0.8);
	border: 1px solid var(--wizard-border, hsl(220 10% 18%));
	border-radius: 0.5rem;
	color: var(--wizard-text-muted, hsl(220 10% 60%));
	font-size: 0.75rem;
	font-weight: 500;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	cursor: pointer;
	transition: all 0.15s ease;
	backdrop-filter: blur(8px);
	min-height: 2rem;
	min-width: 2rem;
}

.lang-trigger:hover {
	background: hsl(220 15% 14% / 0.9);
	border-color: var(--wizard-accent, hsl(45 90% 55%));
	color: var(--wizard-text, hsl(220 10% 92%));
}

.lang-trigger:focus-visible {
	outline: 2px solid var(--wizard-focus-ring, hsl(45 90% 55% / 0.5));
	outline-offset: 2px;
}

.lang-icon {
	width: 1rem;
	height: 1rem;
	flex-shrink: 0;
}

.lang-code {
	line-height: 1;
}

.lang-chevron {
	width: 0.75rem;
	height: 0.75rem;
	flex-shrink: 0;
	transition: transform 0.15s ease;
}

.lang-chevron.open {
	transform: rotate(180deg);
}

.lang-menu {
	position: absolute;
	top: calc(100% + 4px);
	right: 0;
	min-width: 100%;
	background: hsl(220 15% 10% / 0.95);
	border: 1px solid var(--wizard-border, hsl(220 10% 18%));
	border-radius: 0.5rem;
	padding: 0.25rem;
	backdrop-filter: blur(12px);
	box-shadow: 0 8px 24px hsl(0 0% 0% / 0.4);
	animation: menu-enter 0.15s ease-out;
}

.lang-option {
	display: block;
	width: 100%;
	padding: 0.5rem 0.75rem;
	background: transparent;
	border: none;
	border-radius: 0.375rem;
	color: var(--wizard-text-muted, hsl(220 10% 60%));
	font-size: 0.75rem;
	font-weight: 500;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	text-align: left;
	cursor: pointer;
	transition: all 0.1s ease;
	white-space: nowrap;
}

.lang-option:hover {
	background: hsl(220 15% 16%);
	color: var(--wizard-text, hsl(220 10% 92%));
}

.lang-option:focus-visible {
	outline: 2px solid var(--wizard-focus-ring, hsl(45 90% 55% / 0.5));
	outline-offset: -2px;
}

.lang-option.active {
	color: var(--wizard-accent, hsl(45 90% 55%));
}

@keyframes menu-enter {
	from {
		opacity: 0;
		transform: translateY(-4px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

@media (prefers-reduced-motion: reduce) {
	.lang-chevron,
	.lang-trigger {
		transition: none;
	}

	.lang-menu {
		animation: none;
	}
}
</style>
