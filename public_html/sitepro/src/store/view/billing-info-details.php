<?php
/**
 * @var $this StoreElement
 * @var string $title
 * @var string $source
 * @var bool $needPhone
 * @var array $billingFields
 */

?>
<h3 style="margin-bottom: 20px; font-weight: bold;" class="wb-store-sys-text"><?php echo $title; ?></h3>
<div class="row">
	<div class="col-xs-12 wb-store-sys-text">
		<?php foreach ($billingFields as $idx => $field) {
			if (!$field->enabled) continue;

			if (!isset($field->showFor) || $field->showFor === 'both') {
				$showFor = '1';
			} elseif ($field->showFor === 'company') {
				$showFor = $source . '.isCompany';
			} elseif ($field->showFor === 'personal') {
				$showFor = '!' . $source . '.isCompany';
			}

			?>
			<div data-ng-if="<?php echo $showFor ?>">
			<?php
			switch ($field->type) {
				case 'input':
				case 'textarea':
				case 'select':
				case "number":
				case "email":
				case "phone":
				case "date":
					?>
					<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>Pure.<?php echo 'wb_input_' . $idx ?> || '–'}}<br/>
					<?php
					break;

				case 'checkbox':
					if (!isset($field->settings->options) || count($field->settings->options) <= 0 || (count($field->settings->options) === 1 && empty($field->settings->options[0]))) {
						?>
						<label data-ng-if="<?php echo $source; ?>.<?php echo 'wb_input_' . $idx ?>" class="wb-store-sys-text"><?php echo $field->name; ?></label><br/>
						<?php
					} else {
						?>
						<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{ main.getOptionsText(<?php echo $source; ?>Pure, <?php echo $idx ?>) }}<br/>
						<?php
					}
					break;
				case "radiobox":
					if (isset($field->settings->options) && (count($field->settings->options) > 1 || (count($field->settings->options) === 1 && !empty($field->settings->options[0])))) {
						?>
						<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{ main.getOptionsText(<?php echo $source; ?>Pure, <?php echo $idx ?>) }}<br/>
						<?php
					}
					break;

				case "range":
					?>
					<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>Pure.<?php echo 'wb_input_' . $idx ?> || '–'}}<br/>
					<?php
					break;

				case "wb_store_isCompany":
					break;
				case "wb_store_email":
					?>
					<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.email || '–'}}<br/>
					<?php
					break;
				case "wb_store_phone":
					if (isset($needPhone) && $needPhone) { ?>
						<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.phone || '–'}}<br/>
					<?php }
					break;
				case "wb_store_firstName":
					?>
					<div>
						<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.firstName || '–'}}<br/>
					</div>
					<?php
					break;
				case "wb_store_lastName":
					?>
					<div>
						<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.lastName || '–'}}<br/>
					</div>
					<?php
					break;
				case "wb_store_companyName":
					?>
					<div>
						<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.companyName || '–'}}<br/>
					</div>
					<?php
					break;
				case "wb_store_companyCode":
					?>
					<div>
						<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.companyCode || '–'}}<br/>
					</div>
					<?php
					break;
				case "wb_store_companyVatCode":
					?>
					<div>
						<span data-ng-if="<?php echo $source; ?>.companyVatCode"><label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.companyVatCode || '–'}}<br/></span>
					</div>
					<?php
					break;
				case "wb_store_address1":
					?>
					<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.address1 || '–'}}<br/>
					<?php
					break;
				case "wb_store_city":
					?>
					<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.city || '–'}}<br/>
					<?php
					break;
				case "wb_store_postCode":
					?>
					<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.postCode || '–'}}<br/>
					<?php
					break;
				case "wb_store_countryCode":
					?>
					<label class="wb-store-sys-text"><?php echo $field->name; ?>:</label> {{<?php echo $source; ?>.country || '–'}}<br/>
					<?php
					break;
				case "wb_store_region":
					?>
					<label class="wb-store-sys-text" data-ng-hide="<?php echo $source; ?>.countryCode === 'US' || <?php echo $source; ?>.countryCode === 'NG'"><?php echo $this->__('Region'); ?>:</label><label class="wb-store-sys-text" data-ng-show="<?php echo $source; ?>.countryCode === 'US' || <?php echo $source; ?>.countryCode === 'NG'"><?php echo $this->__('State / Province'); ?>:</label> {{<?php echo $source; ?>.region || '–'}}<br/>
					<?php
					break;
					?>
			<?php } ?>
			</div>
		<?php } ?>
	</div>
</div>
