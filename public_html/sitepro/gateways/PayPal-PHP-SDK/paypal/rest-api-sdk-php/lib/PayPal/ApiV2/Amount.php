<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalModel;
use PayPal\Converter\FormatConverter;
use PayPal\Validation\NumericValidator;

/**
 * Class Amount
 *
 * payment amount with break-ups.
 *
 * @package PayPal\ApiV2
 *
 * @property string currency_code
 * @property string value
 * @property \PayPal\ApiV2\Breakdown breakdown
 */
class Amount extends PayPalModel
{
	/**
	 * 3-letter [currency code](https://developer.paypal.com/docs/integration/direct/rest_api_payment_country_currency_support/). PayPal does not support all currencies.
	 *
	 * @param string $currency
	 *
	 * @return $this
	 */
	public function setCurrencyCode($currency)
	{
		$this->currency_code = $currency;
		return $this;
	}

	/**
	 * 3-letter [currency code](https://developer.paypal.com/docs/integration/direct/rest_api_payment_country_currency_support/). PayPal does not support all currencies.
	 *
	 * @return string
	 */
	public function getCurrencyCode()
	{
		return $this->currency_code;
	}

	/**
	 * Total amount charged from the payer to the payee. In case of a refund, this is the refunded amount to the original payer from the payee. 10 characters max with support for 2 decimal places.
	 *
	 * @param string|double $value
	 *
	 * @return $this
	 */
	public function setValue($value)
	{
		NumericValidator::validate($value, "Value");
		$value = FormatConverter::formatToPrice($value, $this->getCurrencyCode());
		$this->value = $value;
		return $this;
	}

	/**
	 * Total amount charged from the payer to the payee. In case of a refund, this is the refunded amount to the original payer from the payee. 10 characters max with support for 2 decimal places.
	 *
	 * @return string
	 */
	public function getValue()
	{
		return $this->value;
	}

	/**
	 * @param \PayPal\ApiV2\Breakdown $breakdown
	 *
	 * @return $this
	 */
	public function setBreakdown($breakdown)
	{
		$this->breakdown = $breakdown;
		return $this;
	}

	/**
	 * @return \PayPal\ApiV2\Breakdown
	 */
	public function getBreakdown()
	{
		return $this->breakdown;
	}
}
