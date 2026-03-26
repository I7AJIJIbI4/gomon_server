<?php
/**
 * @var StoreInvoiceApi $this
 * @var StoreModuleOrder $order
 * @var string|string[]|null $sellerCompanyInfo
 * @var string|string[]|null $invoiceTextBeginning
 * @var string|string[]|null $invoiceTextEnding
 * @var string|string[]|null $invoiceTitlePhrase
 * @var string|null $logoImage
 * @var string|null $logoImageAlign
 * @var string|null $formattedDate
 * @var string $fileDownloadUrl
 */
?>

<html>
<head>

</head>
<body style="text-align: center;display: flex;justify-content: center;">
<div style="display: flex;flex-direction: column;align-items: center;max-width: 700px;width: 100%">
	<?php if ($logoImage): ?>
		<p style="text-align: <?php echo $logoImageAlign; ?>;">
			<img src="<?php echo $logoImage; ?>">
		</p>
	<?php endif; ?>

	<p style="text-align: center;">
		<strong style="font-size: 12;"><?php echo StoreInvoice::fontize(htmlspecialchars(trim(tr_(isset($invoiceTitlePhrase) ? $invoiceTitlePhrase : StoreModule::__('Invoice'))))); ?> <?php echo StoreInvoice::fontize(htmlspecialchars($order->getInvoiceDocumentNumber())); ?></strong><br />
		<?php echo $formattedDate; ?>
	</p>
	<p></p>

	<?php if (isset($invoiceTextBeginning) && $invoiceTextBeginning && ($v = trim(tr_($invoiceTextBeginning)))): ?>
		<div><?php echo StoreInvoice::fontize($v); ?></div>
	<?php endif; ?>

	<table border="1" cellpadding="3">
		<thead>
		<tr>
			<th style="width: 15%; font-weight: bold;"><?php echo StoreInvoice::fontize(StoreModule::__('SKU')); ?></th>
			<th style="width: 60%; font-weight: bold;"><?php echo StoreInvoice::fontize(StoreModule::__('Product description')); ?></th>
			<th style="width: 10%; font-weight: bold;"><?php echo StoreInvoice::fontize(StoreModule::__('Qty')); ?></th>
			<th style="width: 15%; font-weight: bold;"><?php echo StoreInvoice::fontize(StoreModule::__('Price')); ?></th>
		</tr>
		</thead>
		<tbody>
		<?php foreach( $order->getItems() as $item ) { ?>
			<tr style="page-break-inside: avoid;">
				<td style="width: 15%;"><?php echo StoreInvoice::fontize(htmlspecialchars($item->sku)); ?></td>
				<td style="width: 60%;"><?php echo StoreInvoice::fontize(htmlspecialchars(tr_($item->name))); ?></td>
				<td style="width: 10%;"><?php echo $item->quantity; ?></td>
				<td style="width: 15%;"><?php echo StoreInvoice::fontize(htmlspecialchars($item->getFormattedPrice())); ?></td>
			</tr>
		<?php } ?>
		</tbody>
	</table>
	<p></p>
	<table border="1" cellpadding="3" style="page-break-inside: avoid;">
		<tbody>
		<?php if ($order->getFullTaxAmount() > 0 || $order->getShippingAmount() || $order->getDiscountAmount()) { ?>
			<tr>
				<td style="width: 85%;"><strong><?php echo StoreInvoice::fontize(StoreModule::__('Subtotal')); ?>:</strong></td>
				<td style="width: 15%;"><?php echo StoreInvoice::fontize(htmlspecialchars(StoreData::formatPrice($order->getPrice() + $order->getDiscountAmount() - $order->getFullTaxAmount() - $order->getShippingAmount(), $order->getPriceOptions(), $order->getCurrency()))); ?></td>
			</tr>
		<?php } ?>
		<?php if ($order->getDiscountAmount()) { ?>
			<tr>
				<td style="width: 85%;"><strong><?php echo StoreInvoice::fontize(StoreModule::__('Discount')); ?>:</strong></td>
				<td style="width: 15%;"><?php echo StoreInvoice::fontize(htmlspecialchars('-'.StoreData::formatPrice($order->getDiscountAmount(), $order->getPriceOptions(), $order->getCurrency()))); ?></td>
			</tr>
		<?php } ?>
		<?php if( $order->getShippingAmount() ) { ?>
			<tr>
				<td style="width: 85%;"><strong><?php echo StoreInvoice::fontize(StoreModule::__('Shipping')); ?>:</strong> (<?php echo StoreInvoice::fontize(htmlspecialchars($order->getShippingDescription())); ?>)</td>
				<td style="width: 15%;"><?php echo StoreInvoice::fontize(htmlspecialchars(StoreData::formatPrice($order->getShippingAmount(), $order->getPriceOptions(), $order->getCurrency()))); ?></td>
			</tr>
		<?php } ?>
		<?php if ($order->getFullTaxAmount() > 0): ?>
			<?php foreach ($order->getTaxes() as $tax): ?>
				<tr>
					<td style="width: 85%;"><strong><?php
							echo StoreInvoice::fontize(($tax->shippingOnly ? StoreModule::__('Shipping Tax') : StoreModule::__('Tax')))
								.($tax->rate > 0 ? " ({$tax->getRatePercent()}%)" : "");
							?>:</strong></td>
					<td style="width: 15%;"><?php
						echo StoreInvoice::fontize(htmlspecialchars(StoreData::formatPrice($tax->amount, $order->getPriceOptions(), $order->getCurrency())));
						?></td>
				</tr>
			<?php endforeach; ?>
		<?php endif; ?>
		<tr>
			<td style="width: 85%;"><strong><?php echo StoreInvoice::fontize(StoreModule::__('Total')); ?>:</strong></td>
			<td style="width: 15%;"><?php echo StoreInvoice::fontize(htmlspecialchars(StoreData::formatPrice($order->getPrice(), $order->getPriceOptions(), $order->getCurrency()))); ?></td>
		</tr>
		</tbody>
	</table>
	<p></p>
	<table>
		<tbody>
			<?php foreach ($order->getItems() as $item) { ?>
				<?php foreach ($item->files as $file) { ?>
					<tr>
						<td colspan="2">
							<a href="<?php echo $fileDownloadUrl . '/' . $file->name ?>" target="_blank" title="<?php echo $file->name ?>">
								<?php echo StorePaymentApi::safeEmailText((string)$file); ?>
							</a>
						</td>
					</tr>
				<?php } ?>
			<?php } ?>
		</tbody>
	</table>

	<?php if (isset($invoiceTextEnding) && $invoiceTextEnding && ($v = trim(tr_($invoiceTextEnding)))): ?>
		<div><?php echo StoreInvoice::fontize($v); ?></div>
	<?php endif; ?>
</div>
</body>
</html>
