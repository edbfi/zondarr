<script lang="ts">
interface Props {
	onsubmit: (code: string) => void;
	disabled?: boolean;
}

const { onsubmit, disabled = false }: Props = $props();

const DIGITS = 6;
let digits = $state<string[]>(Array(DIGITS).fill(''));
let inputRefs = $state<(HTMLInputElement | null)[]>(Array(DIGITS).fill(null));

const code = $derived(digits.join(''));
const isFilled = $derived(code.length === DIGITS && /^\d{6}$/.test(code));

$effect(() => {
	if (isFilled && !disabled) {
		onsubmit(code);
	}
});

function handleInput(index: number, e: Event) {
	const input = e.target as HTMLInputElement;
	const value = input.value;

	// Only accept single digit
	if (/^\d$/.test(value)) {
		digits[index] = value;
		// Auto-advance to next input
		if (index < DIGITS - 1) {
			inputRefs[index + 1]?.focus();
		}
	} else {
		// Reset if non-digit
		digits[index] = '';
		input.value = '';
	}
}

function handleKeydown(index: number, e: KeyboardEvent) {
	if (e.key === 'Backspace') {
		if (digits[index]) {
			digits[index] = '';
		} else if (index > 0) {
			// Move back to previous input
			digits[index - 1] = '';
			inputRefs[index - 1]?.focus();
		}
		e.preventDefault();
	} else if (e.key === 'ArrowLeft' && index > 0) {
		inputRefs[index - 1]?.focus();
	} else if (e.key === 'ArrowRight' && index < DIGITS - 1) {
		inputRefs[index + 1]?.focus();
	}
}

function handlePaste(e: ClipboardEvent) {
	e.preventDefault();
	const pasted = (e.clipboardData?.getData('text') ?? '').trim();
	const cleaned = pasted.replace(/\D/g, '').slice(0, DIGITS);

	if (cleaned.length === 0) return;

	for (let i = 0; i < DIGITS; i++) {
		digits[i] = cleaned[i] ?? '';
	}

	// Focus the next empty input or the last one
	const nextEmpty = digits.indexOf('');
	const focusIndex = nextEmpty === -1 ? DIGITS - 1 : nextEmpty;
	inputRefs[focusIndex]?.focus();
}

function handleFocus(e: FocusEvent) {
	(e.target as HTMLInputElement).select();
}

export function reset() {
	digits = Array(DIGITS).fill('');
	inputRefs[0]?.focus();
}

export function focus() {
	inputRefs[0]?.focus();
}
</script>

<!-- biome-ignore lint/a11y/useSemanticElements: This ARIA group labels existing controls without introducing native fieldset layout. -->
<div class="flex justify-center gap-2" role="group" aria-label="TOTP verification code">
	{#each { length: DIGITS } as _, i}
		<input
			bind:this={inputRefs[i]}
			type="text"
			inputmode="numeric"
			autocomplete="one-time-code"
			maxlength={1}
			value={digits[i]}
			{disabled}
			oninput={(e) => handleInput(i, e)}
			onkeydown={(e) => handleKeydown(i, e)}
			onpaste={handlePaste}
			onfocus={handleFocus}
			aria-label={`Digit ${i + 1}`}
			class="h-12 w-10 rounded-md border border-cr-border bg-cr-bg text-center text-lg font-mono text-cr-text outline-none transition-colors focus:border-cr-accent focus:ring-1 focus:ring-cr-accent disabled:cursor-not-allowed disabled:opacity-50"
		>
	{/each}
</div>
