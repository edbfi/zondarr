<script lang="ts">
import { RadioGroup as RadioGroupPrimitive } from 'bits-ui';
import { cn, type WithoutChildrenOrChild } from '$lib/utils.js';

let {
	ref = $bindable(null),
	class: className,
	...restProps
}: WithoutChildrenOrChild<RadioGroupPrimitive.ItemProps> = $props();
</script>

<RadioGroupPrimitive.Item
	bind:ref
	data-slot="radio-group-item"
	class={cn(
	'border-input text-primary focus-visible:border-ring focus-visible:ring-ring/50 aria-checked:border-primary aspect-square size-4 shrink-0 rounded-full border shadow-xs transition-all outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50',
	className
)}
	{...restProps}
>
	{#snippet children({
	checked
})}
		{#if checked}
			<span class="flex items-center justify-center">
				<span class="size-2 rounded-full bg-primary"></span>
			</span>
		{/if}
	{/snippet}
</RadioGroupPrimitive.Item>
