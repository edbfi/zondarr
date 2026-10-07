<script lang="ts">
import { Check } from '@lucide/svelte';

interface Props {
	currentStep: number;
	totalSteps: number;
	stepLabels: string[];
}

const { currentStep, totalSteps, stepLabels }: Props = $props();
</script>

<div class="step-indicator flex items-center justify-center gap-0 py-4">
	{#each { length: totalSteps } as _, i}
		{@const stepNum = i + 1}
		{@const isCompleted = stepNum < currentStep}
		{@const isCurrent = stepNum === currentStep}
		{@const isFuture = stepNum > currentStep}

		<!-- Step circle + label -->
		<div class="flex flex-col items-center gap-1.5">
			<div
				class="relative flex size-8 items-center justify-center rounded-full border-2 transition-all duration-300
					{isCompleted ? 'border-cr-accent bg-cr-accent text-cr-bg' : ''}
					{isCurrent ? 'border-cr-accent bg-cr-accent/10 text-cr-accent' : ''}
					{isFuture ? 'border-cr-border bg-cr-bg text-cr-text-dim' : ''}"
			>
				{#if isCompleted}
					<Check class="size-4" />
				{:else}
					<span class="font-mono text-xs font-semibold">{stepNum}</span>
				{/if}
				{#if isCurrent}
					<span
						class="absolute inset-0 animate-ping rounded-full border border-cr-accent/30"
					></span>
				{/if}
			</div>
			<span
				class="text-xs font-medium uppercase tracking-wider font-mono
					{isCurrent || isCompleted ? 'text-cr-text' : 'text-cr-text-dim'}"
			>
				{stepLabels[i]}
			</span>
		</div>

		<!-- Connector track -->
		{#if i < totalSteps - 1}
			<div class="mx-2 mb-6 h-0.5 w-12 sm:w-16">
				<div
					class="h-full rounded-full transition-all duration-500
						{stepNum < currentStep ? 'bg-cr-accent' : 'bg-cr-border'}"
				></div>
			</div>
		{/if}
	{/each}
</div>
