<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalModel;

/**
 * Class ItemList
 *
 * List of items being paid for.
 *
 * @package PayPal\ApiV2
 *
 * @property string reference_id
 * @property string description
 * @property string custom_id
 * @property string invoice_id
 * @property string soft_descriptor
 * @property \PayPal\ApiV2\Item[] items
 * @property \PayPal\ApiV2\Amount amount Required
 */
class ItemList extends PayPalModel
{
	/**
	 * List of items.
	 *
	 * @param \PayPal\ApiV2\Item[] $items
	 *
	 * @return $this
	 */
	public function setItems($items)
	{
		$this->items = array_values($items);
		return $this;
	}

	/**
	 * List of items.
	 *
	 * @return \PayPal\ApiV2\Item[]
	 */
	public function getItems()
	{
		return $this->items;
	}

	/**
	 * Append Items to the list.
	 *
	 * @param \PayPal\ApiV2\Item $item
	 * @return $this
	 */
	public function addItem($item)
	{
		if (!$this->getItems()) {
			return $this->setItems(array($item));
		} else {
			return $this->setItems(
				array_merge($this->getItems(), array($item))
			);
		}
	}

	/**
	 * Remove Items from the list.
	 *
	 * @param \PayPal\ApiV2\Item $item
	 * @return $this
	 */
	public function removeItem($item)
	{
		return $this->setItems(
			array_diff($this->getItems(), array($item))
		);
	}

	/**
	 * Amount
	 *
	 * @param \PayPal\ApiV2\Amount $amount
	 *
	 * @return $this
	 */
	public function setAmount($amount)
	{
		$this->amount = $amount;
		return $this;
	}

	/**
	 * Amount
	 *
	 * @return \PayPal\ApiV2\Amount
	 */
	public function getAmount()
	{
		return $this->amount;
	}
}
