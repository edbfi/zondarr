<script lang="ts" module>
import { tv, type VariantProps } from 'tailwind-variants';

export const statusBadgeVariants = tv({
	base: 'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium transition-colors',
	variants: {
		status: {
			active: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
			enabled: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30',
			pending: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
			limited: 'bg-amber-500/15 text-amber-400 border border-amber-500/30',
			disabled: 'bg-rose-500/15 text-rose-400 border border-rose-500/30',
			expired: 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
		}
	},
	defaultVariants: {
		status: 'pending'
	}
});

export type StatusBadgeStatus = VariantProps<typeof statusBadgeVariants>['status'];
</script>

<script lang="ts">
import { cn } from '$lib/utils.js';

interface Props {
	status: StatusBadgeStatus;
	label?: string;
	class?: string;
}

let { status, label, class: className }: Props = $props();

// Derive the display label from status if not provided
let displayLabel = $derived(
	label ?? (status ? status.charAt(0).toUpperCase() + status.slice(1) : 'Unknown')
);

// Derive the dot color class based on status
let dotClass = $derived.by(() => {
	switch (status) {
		case 'active':
		case 'enabled':
			return 'bg-emerald-400 shadow-[0_0_6px_rgba(16,185,129,0.5)]';
		case 'pending':
		case 'limited':
			return 'bg-amber-400 shadow-[0_0_6px_rgba(245,158,11,0.5)]';
		case 'disabled':
		case 'expired':
			return 'bg-rose-400 shadow-[0_0_6px_rgba(244,63,94,0.5)]';
		default:
			return 'bg-zinc-400';
	}
});
</script>

<span data-status-badge data-status={status} class={cn(statusBadgeVariants({ status }), className)}>
	<span class={cn('size-1.5 rounded-full', dotClass)}></span>
	{displayLabel}
</span>
