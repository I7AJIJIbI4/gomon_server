<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalModel;

/**
 * Class PaymentSource
 *
 * PaymentSource details.
 *
 * @package PayPal\ApiV2
 *
 * @property \PayPal\ApiV2\Paypal paypal
 */
class PaymentSource extends PayPalModel
{
	/**
	 * @param \PayPal\ApiV2\Paypal $paypal
	 *
	 * @return $this
	 */
	public function setPaypal($paypal)
	{
		$this->paypal = $paypal;
		return $this;
	}

	/**
	 * @return \PayPal\ApiV2\Paypal
	 */
	public function getPaypal()
	{
		return $this->paypal;
	}
}
