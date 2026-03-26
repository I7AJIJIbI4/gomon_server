<?php
/**
 * @var StoreElement $this
 * @var string $source
 * @var string $errorSource
 * @var string $title
 * @var bool $canSameAsPrev
 * @var bool $needPhone
 * @var bool $limitToAvailableCountries
 **/

$form = '';
if ($hasBillingForm && $hasBillingFormFile) {
    ob_start();
    require $hasBillingFormFile;
	$form = ob_get_clean();
}

$form = strtr($form, [
    '{{ source }}' => $source,
    '{{ errorSource }}' => $errorSource,
    '{{ countriesStr }}' => "main.data.countries" . ( $limitToAvailableCountries ? " | filter:filterAllowedCountries" : ""),
    '{{ regionStr }}' => 'main.getCountry( ' . $source. '.countryCode).regions' . ( $limitToAvailableCountries ? (' | filter:filterAllowedRegions(' .$source . '.countryCode)') : ''),
    '{{ needPhone }}' => (isset($needPhone) && $needPhone) ? 1 : 0,
]);
?>
<h3 style="margin-bottom: 20px;" class="wb-store-sys-text"><?php
	echo $title;
	if (isset($canSameAsPrev) && $canSameAsPrev): ?>
		<div class="checkbox wb-store-cart-same-as-prev-cb wb-store-sys-text" data-ng-class="{'has-error': main.billingInfoErrors.email}"><label>
			<input type="checkbox" class="wb-store-use-save-cb"
				   style="margin-top: 2px;"
				   data-ng-change="main.changeInfoField('hideDeliveryInfo', main.billingInfoErrors); main.changeInfoField('country', main.billingInfoErrors); main.changeInfoField('region', main.billingInfoErrors);"
				   data-ng-model="main.hideDeliveryInfo"/>
			<?php echo $this->__('Same as billing information'); ?>
		</label></div><?php
	endif;
?></h3>
<div style="overflow-x: hidden;">
	<input type="hidden" name="billing-info" value="1"/>

	<div class="wb-store-billing-info-form"<?php if (isset($canSameAsPrev) && $canSameAsPrev): ?> data-ng-hide="main.hideDeliveryInfo"<?php endif; ?>>
		<?php echo $form; ?>
	</div>
</div>
