<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalModel;

/**
 * Class Breakdown
 *
 * @package PayPal\ApiV2
 *
 * @property \PayPal\ApiV2\Amount item_total
 */
class Breakdown extends PayPalModel
{
	/**
	 * @param \PayPal\ApiV2\Amount $item_total
	 *
	 * @return $this
	 */
	public function setItemTotal($item_total)
	{
		$this->item_total = $item_total;
		return $this;
	}

	/**
	 * @return \PayPal\ApiV2\Amount
	 */
	public function getItemTotal()
	{
		return $this->item_total;
	}
}
