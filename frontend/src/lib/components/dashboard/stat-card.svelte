<script lang="ts">
import type { Snippet } from 'svelte';
import * as Card from '$lib/components/ui/card';

interface Props {
	title: string;
	value: number | string;
	subtitle?: string;
	icon: Snippet;
	accentClass?: string;
}

const { title, value, subtitle, icon, accentClass = 'text-cr-accent' }: Props = $props();
</script>

<Card.Root class="border-cr-border bg-cr-surface transition-colors hover:border-cr-accent/20">
	<Card.Content class="pt-6">
		<div class="flex items-start justify-between gap-3 min-w-0">
			<div class="space-y-1 min-w-0">
				<p class="text-sm font-medium text-cr-text-muted">{title}</p>
				<p class="text-3xl font-bold font-display text-cr-text tracking-tight">{value}</p>
				{#if subtitle}
					<p class="text-xs text-cr-text-dim">{subtitle}</p>
				{/if}
			</div>
			<div class={`rounded-lg p-2.5 bg-current/10 ${accentClass}`}>
				{@render icon()}
			</div>
		</div>
	</Card.Content>
</Card.Root>
