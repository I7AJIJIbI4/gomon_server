<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalModel;

/**
 * Class Item
 *
 * Item details.
 *
 * @package PayPal\ApiV2
 *
 * @property string return_url
 * @property string cancel_url
 */
class ExperienceContext extends PayPalModel
{
	/**
	 * @param string $return_url
	 *
	 * @return $this
	 */
	public function setReturnUrl($return_url)
	{
		$this->return_url = $return_url;
		return $this;
	}

	/**
	 * @return string
	 */
	public function getReturnUrl()
	{
		return $this->return_url;
	}

	/**
	 * @param string $cancel_url
	 *
	 * @return $this
	 */
	public function setCancelUrl($cancel_url)
	{
		$this->cancel_url = $cancel_url;
		return $this;
	}

	/**
	 * @return string
	 */
	public function getCancelUrl()
	{
		return $this->cancel_url;
	}
}
