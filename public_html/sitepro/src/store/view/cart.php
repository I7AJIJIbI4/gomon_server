<?php
/**
 * @var $this StoreBaseElement
 * @var string $elementId
 * @var $items \Profis\SitePro\controller\StoreDataItem[]
 * @var $itemsUrl string[]
 * @var array $storeData
 * @var bool $hasPaymentGateways
 * @var string $hasPaymentGatewaysFile
 * @var array $hasPaymentGatewaysParams
 * @var bool $hasForm
 * @var string $hasFormFile
 * @var bool $hasBillingForm
 * @var string $hasBillingFormFile
 * @var string $termsCheckboxText
 * @var string $cartUrl
 * @var string $backUrl
 * spell-checker: ignore btns
 */

?>
<div class="wb-store-cart-details ng-cloak" data-ng-controller="StoreCartCtrl">
	<div class="wb-store-controls">
		<div>
			<button class="wb-store-back btn btn-default" type="button"
					data-ng-click="main.goBack()"><span class="fa fa-chevron-left"></span>&nbsp;<?php echo $this->__('Back'); ?></button>
		</div>
	</div>
	<table class="wb-store-cart-table"
		   data-ng-show="main.flowStep === 0 || main.flowStep === 2 || main.flowStep === 3"
		   data-ng-style="{width: (main.data.items.length == 0) ? '100%' : null}">
		<thead>
			<tr data-ng-if="main.data.items.length > 0">
				<th style="width: 1%;">&nbsp;</th>
				<th>&nbsp;</th>
				<th style="width: 1%;"><?php echo $this->__('Qty'); ?></th>
				<th style="width: 1%;"><?php echo $this->__('Price'); ?></th>
				<th>&nbsp;</th>
			</tr>
			<tr data-ng-if="main.data.items.length === 0"><td colspan="5">&nbsp;</td></tr>
		</thead>
		<tbody>
			<tr class="wb-store-cart-empty" data-ng-if="main.data.items.length === 0">
				<td colspan="5"><?php echo $this->__('The cart is empty'); ?></td>
			</tr>
			<tr data-ng-repeat="item in main.data.items">
				<td class="wb-store-cart-table-img">
                    <a href="{{ main.itemsUrl[item.id] || '#' }}">
                        <div data-ng-style="{'background-image': 'url(' + item.image + ')'}"></div>
                    </a>
				</td>
				<td class="wb-store-cart-table-name">
                    <a href="{{ main.itemsUrl[item.id] || '#' }}">
					    {{item.name}}
                    </a>
					<span data-ng-if="item.priceStr" class="inline-block">
						({{item.priceStr}}<s data-ng-if="item.priceStr != item.fullPriceStr">{{item.fullPriceStr}}</s>)
					</span>
				</td>
				<td class="wb-store-cart-table-quantity">
					<span class="wb-store-cart-qty-label"><?php echo $this->__('Qty'); ?>:</span>
					<div class="label label-default wb-store-cart-qty-error"
						ng-if="item.quantityError">
						{{item.quantityError}}
					</div>
					<input type="number" class="form-control" min="1" step="1"
						   data-ng-model="item.quantityInput"
						   data-ng-change="main.changeQuantity(item)"
						   data-ng-if="main.flowStep === 0" />
					<span data-ng-if="main.flowStep > 0">{{item.quantity}}</span>
				</td>
				<td class="wb-store-cart-table-price">
					{{item.totalPriceStr}}
				</td>
				<td class="wb-store-cart-table-remove">
					<button class="btn btn-danger" data-ng-if="main.flowStep === 0" data-ng-click="main.removeItem(item)">
						<span title="<?php echo htmlspecialchars($this->__('Remove')); ?>" class="fa fa-trash-o"></span>
					</button>
				</td>
			</tr>
		</tbody>
		<tfoot>
			<tr data-ng-if="main.data.items.length > 0 && main.flowStep === 0 && !main.totals.subTotalPrice.eq(main.totals.totalPrice)">
				<th colspan="3" class="wb-store-cart-table-totals">&nbsp;<?php echo $this->__('Subtotal'); ?>:</th>
				<td class="wb-store-cart-sum">{{main.formatPrice(main.totals.subTotalPrice)}}</td>
				<td>&nbsp;</td>
			</tr>
			<tr data-ng-if="main.data.items.length > 0 && main.flowStep === 0 && main.hasCoupons">
				<th colspan="{{main.coupon ? 3 : 4}}" class="wb-store-cart-table-totals"
					data-ng-style="main.coupon ? {} : {paddingTop: '24px'}">
					&nbsp;<?php echo $this->__('Coupon'); ?>:
					<coupons-control cart="main" style="font-weight: normal;"></coupons-control>
				</th>
				<td class="wb-store-cart-sum" data-ng-if="main.coupon">
					{{main.coupon ? ('-' + main.formatPrice(main.totals.discountPrice)) : ''}}
				</td>
				<td>&nbsp;</td>
			</tr>
			<tr data-ng-if="main.data.items.length > 0 && (main.flowStep === 0 || !main.data.billingShippingRequired)">
				<th colspan="3" class="wb-store-cart-table-totals">&nbsp;<?php echo $this->__('Total'); ?>:</th>
				<td class="wb-store-cart-sum">{{main.formatPrice(main.totals.totalPrice)}}</td>
				<td>&nbsp;</td>
			</tr>
			<tr data-ng-if="main.data.items.length === 0 || (main.flowStep > 0 && main.data.billingShippingRequired)"><td colspan="5">&nbsp;</td></tr>
		</tfoot>
	</table>
	<div data-ng-if="main.flowStep === 1 && main.data.billingShippingRequired">
		<div class="wb-store-cart-forms">
			<div class="wb-store-cart-forms-cont"><?php
				$this->renderView($this->viewPath.'/billing-info-form.php', array(
					'source' => 'main.data.billingInfo',
					'errorSource' => 'main.billingInfoErrors',
					'title' => $this->__('Billing Information'),
					'canSameAsPrev' => false,
					'needPhone' => StoreCartApi::PHONE_FIELD_VISIBLE && StoreCartApi::PHONE_FIELD_REQUIRED, // Phone field MUST be visible in billing info when it is required in shipping info
					'limitToAvailableCountries' => false,
					'hasBillingForm' => $hasBillingForm,
					'hasBillingFormFile' => $hasBillingFormFile,
				));
			?></div>
			<div class="clearfix"></div>
		</div>
		<div class="wb-store-cart-forms" data-ng-if="main.data.deliveryInfoRequired">
			<div class="wb-store-cart-forms-cont"><?php
				$this->renderView($this->viewPath.'/billing-info-form.php', array(
					'source' => 'main.data.deliveryInfo',
					'errorSource' => 'main.deliveryInfoErrors',
					'title' => $this->__('Delivery Information'),
					'canSameAsPrev' => true,
					'needPhone' => StoreCartApi::PHONE_FIELD_VISIBLE,
					'limitToAvailableCountries' => true,
                    'hasBillingForm' => $hasBillingForm,
                    'hasBillingFormFile' => $hasBillingFormFile,
				));
			?></div>
			<div class="clearfix"></div>
		</div>
		<div class="wb-store-cart-forms">
			<div class="wb-store-cart-forms-cont">
				<h3 style="margin-bottom: 20px;" class="wb-store-sys-text"><?php echo $this->__('Order Comments'); ?></h3>
				<div class="form-group">
					<textarea class="form-control"
							  style="height: 114px;"
							  data-ng-model="main.data.orderComment"></textarea>
				</div>
			</div>
			<div class="clearfix"></div>
		</div>
		<div class="wb-store-cart-forms" data-ng-if="main.data.billingShippingRequired && main.data.termsCheckboxEnabled">
			<div class="wb-store-cart-forms-cont" data-ng-class="{'has-error': main.generalErrors.userAgreedToTerms}">
				<div style="padding-left: 20px;">
					<label class="checkbox" style="font-weight: normal;">
						<input type="checkbox"
							   data-ng-model="main.userAgreedToTerms"
							   data-ng-change="main.changeInfoField('userAgreedToTerms', main.generalErrors)"
						/>
						<?php echo $termsCheckboxText; ?>
					</label>
				</div>
			</div>
			<div class="clearfix"></div>
		</div>
		<div class="wb-store-cart-forms">
			<div class="wb-store-cart-forms-cont">
				<div class="alert alert-danger" data-ng-if="main.billingInfoErrors && !main.billingInfoErrors.__isEmpty">
					<button type="button" class="close" data-ng-click="main.billingInfoErrors = null">&times;</button>
					<div data-ng-repeat="error in main.billingInfoErrors">{{error}}</div>
				</div>
				<div class="alert alert-danger" data-ng-if="main.deliveryInfoErrors && !main.deliveryInfoErrors.__isEmpty && !main.hideDeliveryInfo">
					<button type="button" class="close" data-ng-click="main.deliveryInfoErrors = null">&times;</button>
					<div data-ng-repeat="error in main.deliveryInfoErrors">{{error}}</div>
				</div>
				<div class="alert alert-danger" data-ng-if="main.generalErrors && !main.generalErrors.__isEmpty">
					<button type="button" class="close" data-ng-click="main.generalErrors = null">&times;</button>
					<div data-ng-repeat="error in main.generalErrors">{{error}}</div>
				</div>
			</div>
			<div class="clearfix"></div>
		</div>
	</div>
	<div data-ng-if="(main.flowStep === 2 || main.flowStep === 3) && main.data.billingShippingRequired">
		<div class="row-fluid">
			<div class="col-md-4 wb-store-billing-info"><?php
				$this->renderView($this->viewPath.'/billing-info-details.php', array(
					'title' => $this->__('Billing Information'),
					'source' => 'main.data.billingInfo',
					'needPhone' => StoreCartApi::PHONE_FIELD_VISIBLE,

					'billingFields' => $storeData['billingFields'],
				));
				?></div>
			<div class="col-md-4 wb-store-billing-info" data-ng-if="main.data.deliveryInfoRequired"><?php
				$this->renderView($this->viewPath.'/billing-info-details.php', array(
					'title' => $this->__('Delivery Information'),
					'source' => 'main.data.deliveryInfo',
					'needPhone' => StoreCartApi::PHONE_FIELD_VISIBLE,

					'billingFields' => $storeData['billingFields'],
				));
				?></div>
			<div class="col-md-4 wb-store-billing-info">
				<h3 style="margin-bottom: 20px;" class="wb-store-sys-text"><b>{{(main.shippingMethods.length > 0 && main.flowStep === 2) ? <?php echo json_encode($this->__('Shipping Method')); ?> : '&nbsp;'}}</b></h3>
				<div 
					 data-ng-if="main.shippingMethods.length > 0 && main.flowStep === 2">
					<select class="form-control"
							data-ng-options="main.fmtSMN(item, '<?php echo $this->__('days'); ?>') for item in main.shippingMethods"
							data-ng-model="main.shippingMethod"
							data-ng-change="main.applyShipping()"></select>
				</div>
				<div class="wb-store-sys-text" style="margin-top: 16px; margin-bottom: 16px;">
					{{main.getShippingDescription()}}
				</div>
				<div class="wb-store-sys-text"
						data-ng-if="main.shippingMethod && main.flowStep === 3">
					<label class="wb-store-sys-text"><?php echo $this->__('Shipping Method'); ?>:</label>
					{{main.fmtSMN(main.shippingMethod, '<?php echo $this->__('days'); ?>')}}
				</div>
				<div class="wb-store-sys-text"
						style="margin-bottom: 16px;"
						data-ng-if="main.hasCoupons && (main.flowStep === 2 || (main.flowStep === 3 && main.coupon))">
					<label class="wb-store-sys-text"><?php echo $this->__('Coupon'); ?>:</label>
					<coupons-control cart="main"></coupons-control>
				</div>
				<div data-ng-if="!main.totals.subTotalPrice.eq(main.totals.totalPrice)" class="wb-store-sys-text">
					<label class="wb-store-sys-text"><?php echo $this->__('Subtotal'); ?>:</label>&nbsp;{{main.formatPrice(main.totals.subTotalPrice)}}
				</div>
				<div data-ng-if="!main.totals.discountPrice.eq(0)" class="wb-store-sys-text">
					<label class="wb-store-sys-text"><?php echo $this->__('Discount'); ?>:</label>&nbsp;-{{main.formatPrice(main.totals.discountPrice)}}
				</div>
				<div data-ng-if="main.totals.shippingPrice.gt(0)" class="wb-store-sys-text">
					<label class="wb-store-sys-text"><?php echo $this->__('Shipping'); ?>:</label>&nbsp;{{main.formatPrice(main.totals.shippingPrice)}}
				</div>
				<div data-ng-if="main.totals.taxes.length > 0"
						class="wb-store-sys-text"
						data-ng-repeat="tax in main.totals.taxes">
					<label class="wb-store-sys-text">{{tax.shippingOnly ? main.__('Shipping Tax') : main.__('Tax')}} ({{tax.ratePercent}}%):</label>&nbsp;{{main.formatPrice(tax.amount)}}
				</div>
				<div style="font-size: 24px;" class="wb-store-sys-text">
					<label class="wb-store-sys-text"><?php echo $this->__('Total'); ?>:</label>&nbsp;{{main.formatPrice(main.totals.totalPrice)}}
				</div>
			</div>
		</div>
	</div>
<?php if ($hasPaymentGateways || $hasForm): ?>
	<div class="text-center" style="padding-top: 20px; clear: both;" data-ng-if="main.data.items.length > 0 && main.flowStep < 3">
		<?php if( $storeData['minOrderPrice'] ) { ?>
		<div class="wb-store-cart-order-price-too-low" data-ng-show="main.data.minOrderPrice && main.totals.subTotalPrice.lt(main.data.minOrderPrice)"><?php echo sprintf($this->__('Total price of items in the cart should be %s or more'), $this->formatPrice($storeData['minOrderPrice'])); ?></div>
		<?php } ?>
		<button class="btn btn-success btn-lg store-btn" type="button"
				data-ng-disabled="main.loading || (main.data.minOrderPrice && main.totals.subTotalPrice.lt(main.data.minOrderPrice))"
				data-ng-click="main.checkout()">
			{{(main.flowStep === 1 || main.flowStep === 2) ? <?php echo json_encode($this->__('Next Step')); ?> : <?php echo json_encode($this->__('Checkout')); ?>}}
		</button>
	</div>
<?php endif; ?>
<?php if (!$hasPaymentGateways && $hasForm): ?>
	<div class="wb-store-pay-btns" data-ng-show="main.flowStep === 3" data-payment-gateways="false" data-totals="main.totals" data-on-submit="true" data-cart-ctrl="main">
		<?php if ($hasFormFile): ?>
			<?php if (empty($items)): ?> <div style="display: none;"> <?php endif; ?>
				<?php require $hasFormFile; ?>
			<?php if (empty($items)): ?> </div> <?php endif; ?>
		<?php endif; ?>
	</div>
<?php elseif ($hasPaymentGateways): ?>
	<div class="wb-store-pay-wrp" data-ng-if="main.flowStep === 3" data-payment-gateways="true" data-on-submit="main.onPaymentGatewayFormSubmit();" data-cart-ctrl="main">
		<div class="wb-store-pay-sep" style="margin: 0 0 60px 0;"></div>
		<div data-ng-if="!main.data.billingShippingRequired && main.data.termsCheckboxEnabled">
			<div class="row-fluid" style="padding-top: 20px;">
				<div class="col-md-offset-3 col-md-6" data-ng-class="{'has-error': main.generalErrors.userAgreedToTerms}">
					<label style="font-weight: normal;">
						<input type="checkbox"
							   data-ng-model="main.userAgreedToTerms"
							   data-ng-change="main.changeInfoField('userAgreedToTerms', main.generalErrors)"
							   style="vertical-align: -2px; margin: 0;"
						/>
						<?php echo preg_replace('#<p.*>#isuU', '', preg_replace('#</p>#isuU', '<br/>', preg_replace('#</p>\\s*<p.*>#isuU', '<br/><br/>', $termsCheckboxText ?: ''))); ?>
					</label>
				</div>
				<div class="clearfix"></div>
			</div>
			<div class="row-fluid text-left" style="padding-top: 20px;" data-ng-show="main.generalErrors && !main.generalErrors.__isEmpty">
				<div class="col-md-offset-3 col-md-6">
					<div class="alert alert-danger">
						<button type="button" class="close" data-ng-click="main.generalErrors = null">&times;</button>
						<div data-ng-repeat="error in main.generalErrors">{{error}}</div>
					</div>
				</div>
				<div class="clearfix"></div>
			</div>
		</div>
		<p style="margin: 30px 0 -20px; font-size: 11px; text-align: center;"
			data-ng-show="main.data.lang != 'de'"
			class="wb-store-sys-text"><?php echo $this->__('Order with obligation to pay'); ?></p>
		<h3 style="margin: 30px 0 0 0; font-size: 22px; text-align: center;" class="wb-store-sys-text"><?php echo $this->__('Choose Payment Method'); ?></h3>
		<?php $this->renderView($hasPaymentGatewaysFile, $hasPaymentGatewaysParams); ?>
	</div>
<?php endif; ?>
	<div data-ng-if="main.flowStep === 0 && main.data.linkProducts && main.data.linkProducts.length > 0" data-cart-ctrl="main">
		<div class="wb-store-link-list">
			<div class="wb-store-item"
				 data-ng-repeat="item in main.data.linkProducts"
				 data-item-id="{{ item.id }}"
				 data-has-variants="{{ item.hasVariants ? '1' : '0' }}"
				 data-ng-click="main.productClick(item, $event)"
			>
				<div class="wb-store-thumb">
					<a href="{{item.url || '#'}}" data-popup-processed="true">

						<img loading="lazy" src="{{ item.image }}" alt="1">
					</a>
				</div>
				<div class="wb-store-name">
					<a href="{{item.url || '#'}}" data-popup-processed="true">{{ item.name }}</a>
				</div>
				<div class="wb-store-price">
					{{ item.price }}<s data-ng-if="item.minFullPrice">{{ item.minFullPrice }}</s>
					<span data-ng-if="item.minDiscount" class="wb-store-discount-label">
						{{ item.minDiscount }}
					</span>
				</div>
				<div class="wb-store-item-buttons wb-store-remove-from-helper">
					<button class="wb-store-item-add-to-cart btn btn-success btn-xs store-btn"
							data-ng-click="main.productAddToCart(item, $event)">
						{{ main.__('Add to cart') }}
					</button>
				</div>
			</div>
		</div>
	</div>
</div>
<script type="text/javascript">
	$(function() { wb_require(['store/js/StoreCart'], function(app) { app.init('<?php echo $elementId; ?>', '<?php echo $cartUrl; ?>', <?php echo json_encode($storeData); ?>, <?php echo json_encode($itemsUrl); ?>); }); });
</script>
