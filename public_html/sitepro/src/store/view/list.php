<?php
/** @var StoreElement $this */
/** @var StoreNavigation $request */
/** @var \Profis\SitePro\controller\StoreDataItem[] $items */
/** @var \Profis\SitePro\controller\StoreDataCategory[] $categories */
/** @var StoreElementPaging $paging */
/** @var string $filterPosition */
/** @var string $urlAnchor */
/** @var bool $showAddToCartInList */
/** @var bool $showBuyNowInList */
/** @var string $storeShowAddToCartText */
/** @var string $storeShowBuyNowText */
/** @var bool $showCats */
/** @var string $listControls */
/** @var bool $showSorting */
/** @var bool $showViewSwitch */
/** @var bool $showPriceFrom */
/** @var array $itemsStyle */
/** @var string $css */
/** @var bool $thumbAutoCrop */

/** @var string $imageResolution */
/** @var string $thumbResolution */
/** @var \Profis\SitePro\controller\StoreStockSettings $stockSettings */

$pageProp = StoreElementPaging::PAGE_PROP;
$cppProp = StoreElementPaging::CPP_PROP;
?>
<div class="wb-store-filters wb-store-filters-<?php echo $filterPosition; ?>">
	<div>
		<?php if (isset($showCats) && $showCats): ?>
		<div class="col-xs-12 <?php echo ($filterPosition === 'top') ? 'col-sm-6' : ''; ?>">
			<select class="wb-store-cat-select form-control"
					<?php if (isset($filterGroups) && !empty($filterGroups)) echo ' style="margin-bottom: 15px;"'; ?>>
				<option value=""
						data-store-url="<?php echo htmlspecialchars($request->detailsUrl(null, null, true).$urlAnchor); ?>">
					<?php echo $this->__('All'); ?>
				</option>
				<?php foreach ($categories as $item): ?>
				<option value="<?php echo htmlspecialchars($item->id); ?>"
						<?php if ($category && $category->id == $item->id) echo ' selected="selected" '; ?>
						data-store-url="<?php echo htmlspecialchars($request->detailsUrl(null, $item, true).$urlAnchor); ?>">
					<?php echo str_repeat('&nbsp;', $item->indent * 3); ?>
					<?php echo htmlspecialchars($this->noPhp(tr_($item->name))); ?>
				</option>
				<?php endforeach; ?>
			</select>
		</div>
		<?php endif; ?>
		<?php if ($showSorting || $showViewSwitch): ?>
			<div class="col-xs-12 <?php echo ($filterPosition === 'top') ? 'col-sm-6' . ((isset($showCats) && $showCats) ? ' pull-right text-right' : '') : ''; ?>" <?php if (isset($filterGroups) && !empty($filterGroups)) echo ' style="margin-bottom: 15px;"'; ?>>
				<?php if (isset($listControls) && $listControls) require $listControls; ?>
			</div>
		<?php endif; ?>
	</div>
	<?php if (isset($filterGroups) && !empty($filterGroups)): ?>
	<form action="<?php echo htmlspecialchars($serachUrl); ?>" method="get">
		<input type="hidden" name="list" value="<?php echo htmlspecialchars(($tableView ? 'table' : 'list')); ?>" />
		<input type="hidden" name="sort" value="<?php echo htmlspecialchars($sorting ?: ''); ?>" />
		<div>
			<div class="col-xs-12">
				<div class="row">
				<?php
					$columnCoverage = 0;
					foreach ($filterGroups as $filters) {
				?>
					<?php
						foreach ($filters as $filter) {
							$columnBSWidth = preg_match('#\\bcol-(?:xs|sm|md|lg)-(\\d+)\\b#isu', $filter->sizeClass, $mtc) ? intval($mtc[1]) : 12;
							$columnCoverage += $columnBSWidth;
							if( $columnCoverage > 12 ) {
								echo '</div><div class="row">';
								$columnCoverage -= 12;
							}
					?>
					<div class="<?php echo $filter->sizeClass; ?>" style="margin-bottom: 15px;">
						<label style="white-space: nowrap; vertical-align: top;" class="wb-store-sys-text"><?php echo htmlspecialchars($this->noPhp($filter->name)); ?>:</label>
						<?php if ($filter->type == 'dropdown'): ?>
						<select class="form-control"
								name="<?php echo htmlspecialchars('filter['.$filter->id.']'); ?>">
							<option value=""></option>
							<?php foreach ($filter->options as $option): ?>
							<option value="<?php echo htmlspecialchars($option->id); ?>"
									<?php if (isset($filter->value) && $filter->value == $option->id) echo ' selected="selected"'; ?>>
								<?php echo htmlspecialchars($this->noPhp(tr_($option->name))); ?>
							</option>
							<?php endforeach; ?>
						</select>
						<?php elseif ($filter->type == 'checkbox' || $filter->type == 'variant'): ?>
						<div class="wb-store-filters-checkbox-list" style="margin-top: 5px;">
							<?php foreach ($filter->options as $option): ?>
							<label class="checkbox-inline wb-store-sys-text">
								<input type="checkbox"
									   name="<?php echo htmlspecialchars('filter['.$filter->id.'][]'); ?>"
									   value="<?php echo htmlspecialchars($option->id); ?>"
										   <?php if (isset($filter->value) && in_array($option->id, is_array($filter->value) ? $filter->value : array($filter->value))) echo ' checked="checked"'; ?>/>
								<?php echo htmlspecialchars($this->noPhp(tr_($option->name))); ?>
							</label>
							<?php endforeach; ?>
						</div>
						<?php elseif ($filter->type == 'radiobox'): ?>
						<div class="wb-store-filters-radiobox-list" style="margin-top: 5px;">
							<?php foreach ($filter->options as $option): ?>
							<label class="radio-inline wb-store-sys-text">
								<input type="radio"
									   name="<?php echo htmlspecialchars('filter['.$filter->id.']'); ?>"
									   value="<?php echo htmlspecialchars($option->id); ?>"
										   <?php if (isset($filter->value) && $filter->value == $option->id) echo ' checked="checked"'; ?>/>
								<?php echo $this->noPhp(tr_($option->name)); ?>
							</label>
							<?php endforeach; ?>
						</div>
						<?php elseif ($filter->interval): ?>
						<div class="row">
							<div class="col-xs-6">
								<input class="form-control" type="text"
									   name="<?php echo htmlspecialchars('filter['.$filter->id.'][from]'); ?>"
									   placeholder="<?php echo $this->__('From'); ?>"
									   value="<?php echo htmlspecialchars(isset($filter->value['from']) ? $filter->value['from'] : ''); ?>" />
							</div>
							<div class="col-xs-6">
								<input class="form-control" type="text"
									   name="<?php echo htmlspecialchars('filter['.$filter->id.'][to]'); ?>"
									   placeholder="<?php echo $this->__('Up to'); ?>"
									   value="<?php echo htmlspecialchars(isset($filter->value['to']) ? $filter->value['to'] : ''); ?>" />
							</div>
						</div>
						<?php elseif ($filter->id === 'name'): ?>
                            <input class="form-control" type="text"
                                   name="<?php echo htmlspecialchars('filter['.$filter->id.'][text]'); ?>"
                                   value="<?php echo htmlspecialchars(isset($filter->value['text']) ? $filter->value['text'] : ''); ?>" />
                            <label class="checkbox-inline wb-store-sys-text">
                                <input type="checkbox" name="<?php echo htmlspecialchars('filter['.$filter->id.'][desc]'); ?>" value="1" <?php echo isset($filter->value['desc']) ? 'checked="true"' : "" ?>>
                                <?php echo $this->__('Search in Descriptions'); ?>
                            </label>
						<?php else: ?>
						<input class="form-control" type="text"
							   name="<?php echo htmlspecialchars('filter['.$filter->id.']'); ?>"
							   value="<?php echo htmlspecialchars(isset($filter->value) ? $filter->value : ''); ?>" />
						<?php endif; ?>
					</div>
					<?php } ?>
				<?php } ?>
				</div>
			</div>
		</div>
		<div>
			<div class="col-xs-12">
				<button class="btn btn-success store-btn" type="submit"><?php echo $this->__('Search'); ?></button>
			</div>
		</div>
	</form>
	<?php endif; ?>
	<div class="clearfix"></div>
</div>
<div class="wb-store-list"<?php if ($tableView): ?> style="margin-left: 15px; margin-right: 15px;"<?php endif; ?>>
<?php if ($tableView): ?>
	<table class="wb-store-table table table-condensed table-bordered table-striped">
		<thead>
			<tr>
				<th><?php echo $this->__('Item Name'); ?></th>
				<?php if ($hasPrice): ?>
					<th><?php echo $this->__('Price'); ?></th>
				<?php endif; ?>
				<?php foreach ($tableFields as $field): ?>
				<th><?php echo $this->noPhp($field->name); ?></th>
				<?php endforeach; ?>
				<?php if ($showAddToCartInList) { ?><th width="1"></th><?php } ?>
				<?php if ($showBuyNowInList) { ?><th width="1"></th><?php } ?>
			</tr>
		</thead>
		<tbody>
			<?php foreach ($items as $item): ?>
			<tr class="wb-store-item <?php echo isset($itemsStyle[$item->id]['class']) ? $itemsStyle[$item->id]['class'] : '' ?>"
				<?php echo isset($itemsStyle[$item->id]['data-wb-anim-entry-time']) ? ('data-wb-anim-entry-time="' . $itemsStyle[$item->id]['data-wb-anim-entry-time'] . '"') : '' ?>
				<?php echo isset($itemsStyle[$item->id]['data-wb-anim-entry-delay']) ? ('data-wb-anim-entry-delay="' . $itemsStyle[$item->id]['data-wb-anim-entry-delay'] . '"') : '' ?>
                data-item-id="<?php echo htmlspecialchars($item->id); ?>"
				data-has-variants="<?php echo ($item->hasVariants ? '1' : '0'); ?>"
				onclick="location.href = '<?php echo htmlspecialchars($request->detailsUrl($item).$urlAnchor); ?>';">
				<td>
					<a href="<?php echo htmlspecialchars($request->detailsUrl($item).$urlAnchor); ?>"
					   class="wb-store-table-name-link wb-store-name"
					   title="<?php echo htmlspecialchars(tr_($item->name)); ?>"><?php
						if (isset($item->image->image->$imageResolution)):
						?><div style="background-image: url('<?php echo htmlspecialchars($item->image->image->$imageResolution); ?>');"
							   title="<?php echo htmlspecialchars(tr_($item->name)); ?>"></div><?php
						elseif ($noPhotoImage):
						?><div style="background-image: url('<?php echo htmlspecialchars($noPhotoImage->thumb->$thumbResolution); ?>');"></div><?php
						else:
						?><span class="wb-store-nothumb glyphicon glyphicon-picture"></span><?php
						endif;
						?><span class="wb-store-table-name"><?php echo $this->noPhp(tr_($item->name)); ?></span>
					</a>
				</td>
				<?php if ($hasPrice): ?>
					<td class="wb-store-price">
						<?php if ($item->minPrice): ?>
						<?php
						if ($showPriceFrom) {
							echo(($item->hasVariants && $item->minPrice < $item->maxPrice) ? (StoreModule::__('From') . ' ') : '');
						}
						echo $this->formatPrice($item->minPrice);
						if ($item->minPrice != $item->minFullPrice) {
							echo '<s>'.$this->formatPrice($item->minFullPrice).'</s>';
						}
						if (isset($showDiscountLabel) && $showDiscountLabel && $item->minDiscount > 0) {
							echo '<span class="wb-store-discount-label">'
									."-{$item->minDiscount}%"
								.'</span>';
						}
						?>
						<?php else: ?>
							-
						<?php endif; ?>
					</td>
				<?php endif; ?>
				<?php foreach ($this->tableFieldValues($tableFields, $item) as $field): ?>
				<td><?php echo (isset($field->value) ? $this->noPhp($field->value) : '&mdash;'); ?></td>
				<?php endforeach; ?>
				<?php if ($showAddToCartInList) { ?>
					<td width="1" class="wb-store-remove-from-helper">
						<?php if ($item->minPrice): ?>
						<?php if ($item->stockManaged && $item->maxQuantity <= 0): ?>
							<?php if (!$showBuyNowInList): ?>
							<div class="label label-default">
								<?php echo StoreModule::__('Out of stock'); ?>
							</div>
							<?php endif; ?>
						<?php else: ?>
							<button class="wb-store-item-add-to-cart btn btn-success btn-xs store-btn"><?php 
							$addToCart = StoreModule::__($storeShowAddToCartText);
							if (!$addToCart) {
								$addToCart = StoreModule::__('Add to cart');
							}
							echo $addToCart;
							?></button>
						<?php endif; ?>
						<?php else: ?>
							-
						<?php endif; ?>
					</td>
				<?php } ?>
				<?php if ($showBuyNowInList) { ?>
					<td width="1" class="wb-store-remove-from-helper">
						<?php if ($item->minPrice): ?>
						<?php if ($item->stockManaged && $item->maxQuantity <= 0): ?>
							<div class="label label-default">
								<?php echo StoreModule::__('Out of stock'); ?>
							</div>
						<?php else: ?>
							<button class="wb-store-item-buy-now btn btn-success btn-xs"><?php 
								$buyNow = StoreModule::__($storeShowBuyNowText);
								if (!$buyNow) {
									$buyNow = StoreModule::__('Buy Now');
								}
								echo $buyNow;
							?></button>
						<?php endif; ?>
						<?php endif; ?>
					</td>
				<?php } ?>
			</tr>
			<?php endforeach; ?>
		</tbody>
	</table>
<?php else: ?>
	<?php if (!empty($items)): ?>
	<div>
		<?php foreach ($items as $item): ?>
		<div class="wb-store-item <?php echo isset($itemsStyle[$item->id]['class']) ? $itemsStyle[$item->id]['class'] : '' ?>"
			<?php echo isset($itemsStyle[$item->id]['data-wb-anim-entry-time']) ? ('data-wb-anim-entry-time="' . $itemsStyle[$item->id]['data-wb-anim-entry-time'] . '"') : '' ?>
			<?php echo isset($itemsStyle[$item->id]['data-wb-anim-entry-delay']) ? ('data-wb-anim-entry-delay="' . $itemsStyle[$item->id]['data-wb-anim-entry-delay'] . '"') : '' ?>
			 data-item-id="<?php echo htmlspecialchars($item->id); ?>"
			 data-has-variants="<?php echo ($item->hasVariants ? '1' : '0'); ?>"
			 onclick="location.href = '<?php echo htmlspecialchars($request->detailsUrl($item).$urlAnchor); ?>';">
			<div class="wb-store-thumb<?php echo $thumbAutoCrop ? '' : ' wb-store-thumb-contain'; ?>">
				<a href="<?php echo htmlspecialchars($request->detailsUrl($item).$urlAnchor); ?>">

				<?php if (isset($item->image->type) && $item->image->type == 'video' ): ?>
					<video src="<?php echo htmlspecialchars($item->image->src); ?>" muted>
				<?php else: ?>
					<?php if (isset($showDiscountLabel) && $showDiscountLabel && $item->minDiscount > 0): ?>
						<span class="wb-store-discount-label"><?php echo "-{$item->minDiscount}%"; ?></span>
					<?php endif; ?>
					<?php if (isset($item->image->thumb->$thumbResolution)): ?>
					<img loading="lazy" src="<?php echo htmlspecialchars($item->image->thumb->$thumbResolution); ?>"
						alt="<?php echo htmlspecialchars(tr_($item->name) ?: ''); ?>" />
					<?php elseif ($noPhotoImage): ?>
					<img loading="lazy" src="<?php echo htmlspecialchars($noPhotoImage->thumb->$thumbResolution); ?>" alt="" />
					<?php else: ?>
					<span class="wb-store-nothumb glyphicon glyphicon-picture"></span>
					<?php endif; ?>
				<?php endif; ?>

				</a>
			</div>
			<div class="wb-store-name">
				<a href="<?php echo htmlspecialchars($request->detailsUrl($item).$urlAnchor); ?>"><?php echo htmlspecialchars($this->noPhp(tr_($item->name))); ?></a>
			</div>
			<?php if ($item->minPrice && $this->formatPrice($item->minPrice)): ?>
				<div class="wb-store-price"><?php
					if ($showPriceFrom) {
						echo(($item->hasVariants && $item->minPrice < $item->maxPrice) ? (StoreModule::__('From') . ' ') : '');
					}
					echo $this->formatPrice($item->minPrice);
					if ($item->minPrice != $item->minFullPrice) {
						echo '<s>'.$this->formatPrice($item->minFullPrice).'</s>';
					}
				?></div>
			<?php endif; ?>
			<?php if (($showAddToCartInList || $showBuyNowInList) && ($item->minPrice || !$this->options->hasPaymentGateways)) { ?>
				<div class="wb-store-item-buttons wb-store-remove-from-helper">
				<?php if ($item->stockManaged && $item->maxQuantity <= 0): ?>
					<div class="label label-default">
						<?php echo StoreModule::__('Out of stock'); ?>
					</div>
				<?php else: ?>
					<?php if ($showAddToCartInList) { ?>
						<button class="wb-store-item-add-to-cart btn btn-success btn-xs store-btn"><?php 
							$addToCart = StoreModule::__($storeShowAddToCartText);
							if (!$addToCart) {
								$addToCart = StoreModule::__('Add to cart');
							}
							echo $addToCart;
						?></button>
					<?php } ?>
					<?php if ($showBuyNowInList) { ?>
						<button class="wb-store-item-buy-now btn btn-success btn-xs store-btn"><?php 
							$buyNow = StoreModule::__($storeShowBuyNowText);
							if (!$buyNow) {
								$buyNow = StoreModule::__('Buy Now');
							}
							echo $buyNow;
						?></button>
					<?php } ?>
				<?php endif; ?>
				</div>
			<?php } ?>
		</div>
		<?php endforeach; ?>
	</div>
	<?php else: ?>
	<p class="wb-store-sys-text"><?php echo StoreModule::__('No items found'); ?>.</p>
	<?php endif; ?>
<?php endif; ?>
<?php if (isset($paging) && $paging && $paging->pageCount > 1): ?>
	<?php
		$queryArray = array_merge(array(), _get());
		unset($queryArray[$pageProp]);
		unset($queryArray[$cppProp]);
		$qs = (count($queryArray)) ? '&'.http_build_query($queryArray) : '';
		$pagingCurrUrl = $currUrl . (preg_match('#\?#', $currUrl) ? '&' : '?');
	?>
	<ul class="pagination">
		<li<?php if ($paging->pageIndex == 0) echo ' class="disabled"'; ?>><a href="<?php echo $pagingCurrUrl; ?><?php echo $pageProp; ?>=<?php echo max($paging->pageIndex, 1); ?>&amp;<?php echo $cppProp; ?>=<?php echo $paging->itemsPerPage; ?><?php echo $qs.$urlAnchor; ?>">&laquo;</a></li>
		<?php if ($paging->startPageIndex > 0): ?>
		<li><a href="<?php echo $pagingCurrUrl; ?><?php echo $pageProp; ?>=1&amp;<?php echo $cppProp; ?>=<?php echo $paging->itemsPerPage; ?><?php echo $qs.$urlAnchor; ?>">1</a></li>
			<?php if ($paging->startPageIndex > 1): ?>
		<li class="disabled"><a href="javascript:void(0)">...</a></li>
			<?php endif; ?>
		<?php endif; ?>
		<?php for ($i = $paging->startPageIndex; $i <= $paging->endPageIndex; $i++): ?>
		<li<?php if ($paging->pageIndex == $i) { echo ' class="active"'; } ?>><a href="<?php echo $pagingCurrUrl; ?><?php echo $pageProp; ?>=<?php echo $i + 1; ?>&amp;<?php echo $cppProp; ?>=<?php echo $paging->itemsPerPage; ?><?php echo $qs.$urlAnchor; ?>"><?php echo $i + 1; ?></a></li>
		<?php endfor; ?>
		<?php if ($paging->endPageIndex < ($paging->pageCount - 1)): ?>
			<?php if ($paging->endPageIndex < ($paging->pageCount - 2)): ?>
		<li class="disabled"><a href="javascript:void(0)">...</a></li>
			<?php endif; ?>
		<li><a href="<?php echo $pagingCurrUrl; ?><?php echo $pageProp; ?>=<?php echo $paging->pageCount; ?>&amp;<?php echo $cppProp; ?>=<?php echo $paging->itemsPerPage; ?><?php echo $qs.$urlAnchor; ?>"><?php echo $paging->pageCount; ?></a></li>
		<?php endif; ?>
		<li<?php if ($paging->pageIndex == ($paging->pageCount - 1)) { echo ' class="disabled"'; } ?>><a href="<?php echo $pagingCurrUrl; ?><?php echo $pageProp; ?>=<?php echo min($paging->pageCount, ($paging->pageIndex + 2)); ?>&amp;<?php echo $cppProp; ?>=<?php echo $paging->itemsPerPage; ?><?php echo $qs.$urlAnchor; ?>">&raquo;</a></li>
	</ul>
<?php endif; ?>
</div>
<script type="text/javascript">
	$(function() { wb_require(['store/js/StoreList'], function(app) { app.init('<?php echo $elementId; ?>', '<?php echo $cartUrl; ?>', <?php echo json_encode($urlAnchor); ?>, {'Added!': <?php echo json_encode($this->__('Added!')); ?>}); }); });
</script>
<style><?php echo $css ?></style>
