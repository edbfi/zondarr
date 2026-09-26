<script lang="ts">
/**
 * Timer Interaction Config Editor
 *
 * Provides admin UI for configuring timer interaction settings.
 */
import { untrack } from 'svelte';
import { Input } from '$lib/components/ui/input';
import { Label } from '$lib/components/ui/label';
import type { ConfigEditorProps } from '../registry';

const { config: rawConfig, onConfigChange, errors }: ConfigEditorProps = $props();

const DEFAULT_DURATION = 10;
const MIN_DURATION = 1;
const MAX_DURATION = 300;

let lastValidValue = $state(DEFAULT_DURATION);
let displayValue = $state(String(DEFAULT_DURATION));

$effect(() => {
	const incoming = (rawConfig.duration_seconds as number | undefined) ?? DEFAULT_DURATION;
	if (incoming !== untrack(() => lastValidValue)) {
		lastValidValue = incoming;
		displayValue = String(incoming);
	}
});

function handleInput(e: Event & { currentTarget: HTMLInputElement }) {
	displayValue = e.currentTarget.value;
	const parsed = parseInt(displayValue, 10);
	if (!Number.isNaN(parsed)) {
		if (parsed >= MIN_DURATION && parsed <= MAX_DURATION) {
			lastValidValue = parsed;
		}
		onConfigChange({ ...rawConfig, duration_seconds: parsed });
	}
}

function handleBlur() {
	const parsed = parseInt(displayValue, 10);
	if (Number.isNaN(parsed) || displayValue.trim() === '') {
		displayValue = String(lastValidValue);
		return;
	}
	const clamped = Math.min(MAX_DURATION, Math.max(MIN_DURATION, parsed));
	if (clamped !== parsed) {
		lastValidValue = clamped;
		displayValue = String(clamped);
		onConfigChange({ ...rawConfig, duration_seconds: clamped });
	}
}
</script>

<div class="flex flex-col gap-2">
	<Label for="duration" class="text-cr-text">Duration (seconds)</Label>
	<Input
		id="duration"
		type="number"
		min={MIN_DURATION}
		max={MAX_DURATION}
		value={displayValue}
		oninput={handleInput}
		onblur={handleBlur}
		class="border-cr-border bg-cr-bg text-cr-text"
	/>
	<p class="text-xs text-cr-text-muted">Minimum 1 second, maximum 300 seconds (5 minutes)</p>
	{#if errors.duration_seconds}
		<p class="text-xs text-destructive">{errors.duration_seconds[0]}</p>
	{/if}
</div>
