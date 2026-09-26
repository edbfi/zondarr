<script lang="ts">
import { RadioGroup as RadioGroupPrimitive } from 'bits-ui';
import { cn } from '$lib/utils.js';

let {
	ref = $bindable(null),
	class: className,
	...restProps
}: RadioGroupPrimitive.RootProps = $props();
</script>

<RadioGroupPrimitive.Root
	bind:ref
	data-slot="radio-group"
	class={cn('grid gap-3', className)}
	{...restProps}
/>
