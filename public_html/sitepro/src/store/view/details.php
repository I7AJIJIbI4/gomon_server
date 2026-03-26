<?php
/** @var StoreElement $this */
/** @var \Profis\SitePro\controller\StoreDataItem $item */

/** @var \Profis\SitePro\controller\StoreImageData[] $images */
/** @var string $backUrl */

/** @var string $imageResolution */
/** @var string $thumbResolution */
/** @var \Profis\SitePro\controller\StoreStockSettings $stockSettings */
/** @var \Profis\SitePro\controller\StoreDataItemFieldType[] $variants */
?>
<div class="wb-store-details" data-ng-controller="StoreDetailsCtrl">
	<div class="wb-store-controls">
		<div>
			<a class="wb-store-back btn btn-default"
			   href="<?php echo htmlspecialchars($backUrl); ?>"><span class="fa fa-chevron-left"></span>&nbsp;<?php echo $this->__('Back'); ?></a>
		</div>
	</div>
	<div class="wb-store-imgs-block">
		<?php if (!empty($images)): ?>
			<div class="wb-store-image">
				<?php if (isset($showDiscountLabel) && $showDiscountLabel && $item->minDiscount > 0): ?>
					<span class="wb-store-discount-label"><?php echo "-{$item->minDiscount}%"; ?></span>
				<?php endif; ?>
				<?php if (isset($galleryFile) && $galleryFile) require $galleryFile; ?>
			</div>
		<?php else: ?>
			<a class="wb-store-image"
			   href="javascript:void(0)"
			   target="_self">
				<?php if (isset($showDiscountLabel) && $showDiscountLabel && $item->minDiscount > 0): ?>
					<span class="wb-store-discount-label"><?php echo "-{$item->minDiscount}%"; ?></span>
				<?php endif; ?>
				<span class="wb-store-nothumb glyphicon glyphicon-picture"></span>
			</a>
		<?php endif; ?>

		<?php if (0): ?>
			<?php if (isset($images[0]->type) && $images[0]->type == 'video'): ?>
				<a class="wb-store-image" href="javascript:void(0);">
					<?php if (isset($showDiscountLabel) && $showDiscountLabel && $item->minDiscount > 0): ?>
						<span class="wb-store-discount-label"><?php echo "-{$item->minDiscount}%"; ?></span>
					<?php endif; ?>
					<video
						src="<?php echo htmlspecialchars($images[0]->src); ?>"
						alt="<?php echo htmlspecialchars(($v = tr_($images[0]->title)) ? $v : tr_($item->name)); ?>"
						title="<?php echo htmlspecialchars(($v = tr_($images[0]->title)) ? $v : tr_($item->name)); ?>"
						muted>
				</a>
			<?php else: ?>
				<a class="wb-store-image"
				href="<?php echo htmlspecialchars(($v = $images[0]->link ? tr_($images[0]->link->url) : null) ? $v : "javascript:void(0)"); ?>"
				target="<?php echo htmlspecialchars(($v = $images[0]->link ? tr_($images[0]->link->target) : null) ? $v : "_self"); ?>">
					<?php if (isset($showDiscountLabel) && $showDiscountLabel && $item->minDiscount > 0): ?>
						<span class="wb-store-discount-label"><?php echo "-{$item->minDiscount}%"; ?></span>
					<?php endif; ?>
					<?php if (empty($images) || !isset($images[0]->image->$imageResolution)): ?>
					<span class="wb-store-nothumb glyphicon glyphicon-picture"></span>
					<?php else: ?>
					<img loading="lazy" src="<?php echo htmlspecialchars($images[0]->image->$imageResolution); ?>"
						data-zoom-href="<?php echo htmlspecialchars($images[0]->zoom); ?>"
						data-link="<?php echo htmlspecialchars(($v = $images[0]->link ? tr_($images[0]->link->url) : null) ? $v : ""); ?>"
						data-target="<?php echo htmlspecialchars(($v = $images[0]->link ? tr_($images[0]->link->target) : null) ? $v : ""); ?>"
						alt="<?php echo htmlspecialchars(($v = tr_($images[0]->title)) ? $v : tr_($item->name)); ?>"
						title="<?php echo htmlspecialchars(($v = tr_($images[0]->title)) ? $v : tr_($item->name)); ?>" />
					<?php endif; ?>
				</a>
			<?php endif; ?>
			<?php if (count($images) > 1): ?>
			<br/>
			<div class="wb-store-alt-images">
				<?php if (count($images) > 2): ?>
				<span class="arrow-left fa fa-chevron-left"></span>
				<span class="arrow-right fa fa-chevron-right"></span>
				<?php endif; ?>
				<div>
					<div class="wb-store-alt-cont">
						<?php
						foreach ($images as $image): ?>
							<?php if (isset($image->type) && $image->type == 'video'): ?>
								<div class="wb-store-alt-img">
									<video
										src="<?php echo htmlspecialchars($image->src); ?>"
										alt="<?php echo htmlspecialchars(($v = tr_($image->title)) ? $v : tr_($item->name)); ?>"
										title="<?php echo htmlspecialchars(($v = tr_($image->title)) ? $v : tr_($item->name)); ?>"
										style="width: 100%; height: 100%;" muted>
								</div>
							<?php else: ?>
								<?php if (isset($image->image->$imageResolution)): ?>
								<div class="wb-store-alt-img">
									<img loading="lazy" src="<?php echo htmlspecialchars($image->image->$imageResolution); ?>"
										data-zoom-href="<?php echo htmlspecialchars($image->zoom); ?>"
										data-link="<?php echo htmlspecialchars(($v = $image->link ? tr_($image->link->url) : null) ? $v : ""); ?>"
										data-target="<?php echo htmlspecialchars(($v = $image->link ? tr_($image->link->target) : null) ? $v : ""); ?>"
										alt="<?php echo htmlspecialchars(($v = tr_($image->title)) ? $v : tr_($item->name)); ?>"
										title="<?php echo htmlspecialchars(($v = tr_($image->title)) ? $v : tr_($item->name)); ?>" />
								</div>
								<?php endif; ?>
							<?php endif; ?>
						<?php endforeach; ?>
					</div>
				</div>
			</div>
			<?php endif; ?>
		<?php endif; ?>
		<?php if (isset($showDates) && $showDates && isset($item->dateTimeCreated) && $item->dateTimeCreated): ?>
		<div style="color: #c8c8c8; font-weight: normal; font-size: 14px;">
			<?php
				echo $this->__('Created').': '.date('Y-m-d', strtotime($item->dateTimeCreated))
					.((isset($item->dateTimeModified) && $item->dateTimeModified)
						? (' / '.$this->__('Modified').': '.date('Y-m-d', strtotime($item->dateTimeModified)))
						: ''
					);
			?>
		</div>
		<?php endif; ?>
	</div>
	<div class="wb-store-properties">
		<?php echo $renderMicroData(); ?>
		<div class="wb-store-name">
			<?php echo '<' . $tag . '>'; ?>
			<?php echo htmlspecialchars($this->noPhp(tr_($item->name))); ?>
			<?php if (isset($showItemId) && $showItemId): ?><!--
			<span style="color: #c8c8c8; font-weight: normal; font-size: 14px;">(ID: <?php echo $this->noPhp($item->id); ?>)</span>
			--><?php endif; ?>
			<?php echo '</' . $tag . '>'; ?>
		</div>
		
		<table class="wb-store-details-table" style="width: 100%;">
			<tbody>
				<?php if ($cats): ?>
				<tr>
					<td class="wb-store-details-table-field-label">
						<div class="wb-store-pcats"><div class="wb-store-label"><?php echo $this->__('Category'); ?>:</div></div>
					</td>
					<td><div class="wb-store-pcats"><?php echo $this->noPhp($cats); ?></div></td>
				</tr>
				<?php endif; ?>
				
				<?php if ($item->hasVariants || $item->sku): ?>
				<tr class="ng-cloak" <?php echo ($item->hasVariants) ? 'ng-if="ds.variantSkuVal"' : ''; ?> >
					<td class="wb-store-details-table-field-label">
						<div class="wb-store-sku"><div class="wb-store-label"><?php echo $this->__('SKU'); ?>:</div></div>
					</td>
					<td><div class="wb-store-sku"><?php
						echo $item->hasVariants ? '{{ds.variantSkuVal}}' : $this->noPhp($item->sku);
					?></div></td>
				</tr>
				<?php endif; ?>

				<?php if ($item->hasVariants || ($item->minPrice && ($priceStr = $this->formatPrice($item->minPrice)))): ?>
				<tr class="ng-cloak">
					<td class="wb-store-details-table-field-label">
						<div class="wb-store-price"><div class="wb-store-label"><?php echo $this->__('Price'); ?>:</div></div>
					</td>
					<td><div class="wb-store-price"><?php
						if ($item->hasVariants) {
							echo '{{ds.variantPriceVal}}'
								.'<s ng-if="ds.variantPriceVal != ds.variantFullPriceVal">{{ds.variantFullPriceVal}}</s>';
						} else {
							echo $priceStr;
							if ($item->minPrice != $item->minFullPrice) {
								echo '<s>'.$this->formatPrice($item->minFullPrice).'</s> ';
							}
						}
					?></div></td>
				</tr>
				<?php endif; ?>

				<?php foreach ($custFields as $field): ?>
				<tr>
					<td class="wb-store-details-table-field-label">
						<div class="wb-store-field"><div class="wb-store-label"><?php echo htmlspecialchars($this->noPhp($field->name)); ?>:</div></div>
					</td>
					<td><div class="wb-store-field" <?php if (!preg_match("#<(p|u|i|a|b|em|hr|br|ul|li|tr|td|th|h[1-6]|div|span|table|strong)\\b.*>#isuU", $field->value)) echo ' style="white-space: pre-line;"'; ?>><?php echo $field->value; ?></div></td>
				</tr>
				<?php endforeach; ?>

				<tr class="ng-cloak" data-ng-repeat="variant in ds.variants">
					<td class="wb-store-details-table-field-label">
						<div class="wb-store-field">
							<div class="wb-store-label">{{variant.name}}:</div>
						</div>
					</td>
					<td>
						<div class="wb-store-field wb-store-variant">
							<select class="form-control"
								data-ng-if="!variant.subType"
								data-ng-options="opt.name for opt in ds.filterAvailable(variant.options)"
								data-ng-model="ds.variantSelections['#' + variant.id].option">
							</select>
							<div class="wb-store-variant-buttons"
									data-ng-if="variant.subType == 'buttons'"
									data-ng-class="{active: ds.isOptionSelected(variant, opt)}"
									data-ng-click="ds.selectOption(variant, opt)"
									data-ng-repeat="opt in ds.filterAvailable(variant.options)">
								<span>{{opt.name}}</span>
							</div>
							<div class="wb-store-variant-color"
									data-ng-if="variant.subType == 'color'"
									data-ng-class="{active: ds.isOptionSelected(variant, opt)}"
									data-ng-click="ds.selectOption(variant, opt)"
									data-ng-repeat="opt in ds.filterAvailable(variant.options)">
								<div class="tooltip top" role="tooltip">
									<div class="tooltip-arrow"></div>
									<div class="tooltip-inner">{{opt.name}}</div>
								</div>
								<span data-ng-style="opt.value ? {'background-color': opt.value}: {}">
									{{opt.value ? '' : opt.name}}
								</span>
							</div>
							<div class="wb-store-variant-image"
									data-ng-if="variant.subType == 'image'"
									data-ng-class="{active: ds.isOptionSelected(variant, opt)}"
									data-ng-click="ds.selectOption(variant, opt)"
									data-ng-repeat="opt in ds.filterAvailable(variant.options)">
								<div class="tooltip top" role="tooltip">
									<div class="tooltip-arrow"></div>
									<div class="tooltip-inner">{{opt.name}}</div>
								</div>
								<span data-ng-style="opt.value ? {'background-image': 'url(\'' + opt.value + '\')'} : {}">
									{{opt.value ? '' : opt.name}}
								</span>
							</div>
						</div>
					</td>
				</tr>
			</tbody>
		</table>

		<?php if ($hasCart && (!$item->stockManaged || $item->maxQuantity > 0 || $item->hasVariants)): ?>
		<div class="wb-store-form-buttons form-inline ng-cloak"
				data-ng-show="ds.showDetailsButtons">

			<?php if ($item->hasVariants || ($item->minPrice && $priceStr) || !$this->options->hasPaymentGateways): ?>
			<div class="form-group" data-ng-class="{'has-error': ds.addToCartQuantityErr}">
				<input class="wb-store-cart-add-quantity form-control"
					type="number" min="1" step="1" value="1"
					data-ng-model="ds.addToCartQuantityVal" />
			</div>

			<button type="button" class="wb-store-cart-add-btn btn store-btn"
					data-ng-class="[ds.addToCartStyle]"
					data-ng-click="ds.onAddToCart()"
					data-ng-disabled="ds.addToCartQuantityBusy">
				<span data-ng-if="ds.addToCartIcon" data-ng-class="[ds.addToCartIcon]"></span>
				{{ds.addToCartText}}
			</button>
			<?php endif; ?>

			<?php if ($item->stockManaged && $stockSettings->showStockAmount && ($item->maxQuantity > 0 || $item->hasVariants)): ?>
				<div class="form-group wb-store-field"
					<?php if ($item->hasVariants) echo ' data-ng-if="ds.variantQuantityVal"'; ?>>
					<label class="wb-store-label" style="margin: 0 0 0 15px;"><?php echo $this->__('In stock'); ?>:</label>
					<span><?php
						echo $item->hasVariants ? '{{ds.variantQuantityVal}}' : intval($item->quantity);
					?></span>
				</div>
			<?php endif; ?>
		</div>
		<?php endif; ?>
		<?php if ($item->stockManaged && ($item->maxQuantity <= 0 || $item->hasVariants)): ?>
			<div class="label label-default wb-store-no-stock ng-cloak" ng-if="ds.showNoStock">
				<?php echo $this->__('Out of stock'); ?>
			</div>
		<?php endif; ?>

		<?php if (tr_($item->description)): ?>
		<div class="wb-store-desc" style="max-width: 768px;">
			<div class="wb-store-field" style="margin-bottom: 10px;"><div class="wb-store-label"><?php echo $this->__('Description') ?></div></div>
			<?php $description = $this->noPhp(tr_($item->description)); ?>
			<div<?php if (!preg_match("#<(p|u|i|a|b|em|hr|br|ul|li|tr|td|th|h[1-6]|div|span|table|strong)\\b.*>#isuU", $description)) echo ' style="white-space: pre-line;"'; ?>><?php echo $description; ?></div>
		</div>
		<?php endif; ?>
		
		<?php if (!$hasCart && $hasForm): ?>
			<?php if ($hasFormFile) require $hasFormFile; ?>
		<?php endif; ?>
	</div>
</div>
<script type="text/javascript">
	$(function() {
		wb_require(['store/js/StoreDetails'], function(app) {
			app.init(
				<?php echo $this->noPhp(json_encode($elementId)); ?>,
				<?php
					echo $this->noPhp(json_encode((object) array(
						'elementId' => $elementId,
						'itemId' => $item->id,
						'cartUrl' => $cartUrl,
						'variants' => $variants,
						'itemVariants' => $item->hasVariants ? $item->variants : null,
						'isStockManaged' => $item->stockManaged,
						'imageItems' => $jsImages,
						'imageResolution' => $imageResolution,
						'thumbResolution' => $thumbResolution,
						'translations' => array(
							'Add to cart' => $this->__('Add to cart'),
							'Added!' => $this->__('Added!'),
						),
					)));
				?>
			);
		});
	});
</script>
