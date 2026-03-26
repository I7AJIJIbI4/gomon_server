<?php
/**
 * @var string $title
 * @var \Profis\SitePro\controller\StoreDataItem[] $items
 */
?>
<h1><?php echo $title; ?></h1>
<table cellspacing="0" cellpadding="5">
	<tr>
		<th><?php echo StoreModule::__('SKU'); ?></th>
		<th><?php echo StoreModule::__('Name'); ?></th>
		<th><?php echo StoreModule::__('Quantity'); ?></th>
	</tr>
	<?php foreach ($items as $item): ?>
	<tr>
		<td><?php echo htmlspecialchars($item->sku); ?></td>
		<td><?php echo htmlspecialchars(tr_($item->name)); ?></td>
		<td><?php echo htmlspecialchars($item->quantity); ?></td>
	</tr>
	<?php endforeach; ?>
</table>
