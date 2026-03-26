<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalModel;
use PayPal\Converter\FormatConverter;
use PayPal\Validation\NumericValidator;
use PayPal\Validation\UrlValidator;

/**
 * Class Item
 *
 * Item details.
 *
 * @package PayPal\ApiV2
 *
 * @property string sku
 * @property string name Required
 * @property string description
 * @property string quantity Required
 * @property \PayPal\ApiV2\Amount unit_amount Required. Must equal unit_amount * quantity for all items
 * @property string price
 * @property string currency
 * @property string tax
 * @property string url
 */
class Item extends PayPalModel
{
	/**
	 * Stock keeping unit corresponding (SKU) to item.
	 *
	 * @param string $sku
	 *
	 * @return $this
	 */
	public function setSku($sku)
	{
		$this->sku = $sku;
		return $this;
	}

	/**
	 * Stock keeping unit corresponding (SKU) to item.
	 *
	 * @return string
	 */
	public function getSku()
	{
		return $this->sku;
	}

	/**
	 * Item name. 127 characters max.
	 *
	 * @param string $name
	 *
	 * @return $this
	 */
	public function setName($name)
	{
		$this->name = $name;
		return $this;
	}

	/**
	 * Item name. 127 characters max.
	 *
	 * @return string
	 */
	public function getName()
	{
		return $this->name;
	}

	/**
	 * Description of the item. Only supported when the `payment_method` is set to `paypal`.
	 *
	 * @param string $description
	 *
	 * @return $this
	 */
	public function setDescription($description)
	{
		$this->description = $description;
		return $this;
	}

	/**
	 * Description of the item. Only supported when the `payment_method` is set to `paypal`.
	 *
	 * @return string
	 */
	public function getDescription()
	{
		return $this->description;
	}

	/**
	 * Number of a particular item. 10 characters max.
	 *
	 * @param string $quantity
	 *
	 * @return $this
	 */
	public function setQuantity($quantity)
	{
		$this->quantity = $quantity;
		return $this;
	}

	/**
	 * Number of a particular item. 10 characters max.
	 *
	 * @return string
	 */
	public function getQuantity()
	{
		return $this->quantity;
	}

	/**
	 * Number of a particular item. 10 characters max.
	 *
	 * @param \PayPal\ApiV2\Amount $unitAmount
	 *
	 * @return $this
	 */
	public function setUnitAmount($unitAmount)
	{
		$this->unit_amount = $unitAmount;
		return $this;
	}

	/**
	 * Number of a particular item. 10 characters max.
	 *
	 * @return \PayPal\ApiV2\Amount
	 */
	public function getUnitAmount()
	{
		return $this->unit_amount;
	}

	/**
	 * Item cost. 10 characters max.
	 *
	 * @param string|double $price
	 *
	 * @return $this
	 */
	public function setPrice($price)
	{
		NumericValidator::validate($price, "Price");
		$price = FormatConverter::formatToPrice($price, $this->getCurrency());
		$this->price = $price;
		return $this;
	}

	/**
	 * Item cost. 10 characters max.
	 *
	 * @return string
	 */
	public function getPrice()
	{
		return $this->price;
	}

	/**
	 * 3-letter [currency code](https://developer.paypal.com/docs/integration/direct/rest_api_payment_country_currency_support/).
	 *
	 * @param string $currency
	 *
	 * @return $this
	 */
	public function setCurrency($currency)
	{
		$this->currency = $currency;
		return $this;
	}

	/**
	 * 3-letter [currency code](https://developer.paypal.com/docs/integration/direct/rest_api_payment_country_currency_support/).
	 *
	 * @return string
	 */
	public function getCurrency()
	{
		return $this->currency;
	}

	/**
	 * Tax of the item. Only supported when the `payment_method` is set to `paypal`.
	 *
	 * @param string|double $tax
	 *
	 * @return $this
	 */
	public function setTax($tax)
	{
		NumericValidator::validate($tax, "Tax");
		$tax = FormatConverter::formatToPrice($tax, $this->getCurrency());
		$this->tax = $tax;
		return $this;
	}

	/**
	 * Tax of the item. Only supported when the `payment_method` is set to `paypal`.
	 *
	 * @return string
	 */
	public function getTax()
	{
		return $this->tax;
	}

	/**
	 * URL linking to item information. Available to payer in transaction history.
	 *
	 * @param string $url
	 * @return $this
	 * @throws \InvalidArgumentException
	 */
	public function setUrl($url)
	{
		UrlValidator::validate($url, "Url");
		$this->url = $url;
		return $this;
	}

	/**
	 * URL linking to item information. Available to payer in transaction history.
	 *
	 * @return string
	 */
	public function getUrl()
	{
		return $this->url;
	}

	/**
	 * Category type of the item.
	 * Valid Values: ["DIGITAL", "PHYSICAL"]
	 * @param string $category
	 *
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function setCategory($category)
	{
		$this->category = $category;
		return $this;
	}

	/**
	 * Category type of the item.
	 * @return string
	 * @deprecated Not publicly available
	 */
	public function getCategory()
	{
		return $this->category;
	}

	/**
	 * Weight of the item.
	 * @param \PayPal\Api\Measurement $weight
	 *
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function setWeight($weight)
	{
		$this->weight = $weight;
		return $this;
	}

	/**
	 * Weight of the item.
	 * @return \PayPal\Api\Measurement
	 * @deprecated Not publicly available
	 */
	public function getWeight()
	{
		return $this->weight;
	}

	/**
	 * Length of the item.
	 * @param \PayPal\Api\Measurement $length
	 *
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function setLength($length)
	{
		$this->length = $length;
		return $this;
	}

	/**
	 * Length of the item.
	 * @return \PayPal\Api\Measurement
	 * @deprecated Not publicly available
	 */
	public function getLength()
	{
		return $this->length;
	}

	/**
	 * Height of the item.
	 * @param \PayPal\Api\Measurement $height
	 *
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function setHeight($height)
	{
		$this->height = $height;
		return $this;
	}

	/**
	 * Height of the item.
	 * @return \PayPal\Api\Measurement
	 * @deprecated Not publicly available
	 */
	public function getHeight()
	{
		return $this->height;
	}

	/**
	 * Width of the item.
	 * @param \PayPal\Api\Measurement $width
	 *
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function setWidth($width)
	{
		$this->width = $width;
		return $this;
	}

	/**
	 * Width of the item.
	 * @return \PayPal\Api\Measurement
	 * @deprecated Not publicly available
	 */
	public function getWidth()
	{
		return $this->width;
	}

	/**
	 * Set of optional data used for PayPal risk determination.
	 * @param \PayPal\Api\NameValuePair[] $supplementary_data
	 *
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function setSupplementaryData($supplementary_data)
	{
		$this->supplementary_data = $supplementary_data;
		return $this;
	}

	/**
	 * Set of optional data used for PayPal risk determination.
	 * @return \PayPal\Api\NameValuePair[]
	 * @deprecated Not publicly available
	 */
	public function getSupplementaryData()
	{
		return $this->supplementary_data;
	}

	/**
	 * Append SupplementaryData to the list.
	 * @param \PayPal\Api\NameValuePair $nameValuePair
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function addSupplementaryData($nameValuePair)
	{
		if (!$this->getSupplementaryData()) {
			return $this->setSupplementaryData(array($nameValuePair));
		} else {
			return $this->setSupplementaryData(
				array_merge($this->getSupplementaryData(), array($nameValuePair))
			);
		}
	}

	/**
	 * Remove SupplementaryData from the list.
	 * @param \PayPal\Api\NameValuePair $nameValuePair
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function removeSupplementaryData($nameValuePair)
	{
		return $this->setSupplementaryData(
			array_diff($this->getSupplementaryData(), array($nameValuePair))
		);
	}

	/**
	 * Set of optional data used for PayPal post-transaction notifications.
	 * @param \PayPal\Api\NameValuePair[] $postback_data
	 *
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function setPostbackData($postback_data)
	{
		$this->postback_data = $postback_data;
		return $this;
	}

	/**
	 * Set of optional data used for PayPal post-transaction notifications.
	 * @return \PayPal\Api\NameValuePair[]
	 * @deprecated Not publicly available
	 */
	public function getPostbackData()
	{
		return $this->postback_data;
	}

	/**
	 * Append PostbackData to the list.
	 * @param \PayPal\Api\NameValuePair $nameValuePair
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function addPostbackData($nameValuePair)
	{
		if (!$this->getPostbackData()) {
			return $this->setPostbackData(array($nameValuePair));
		} else {
			return $this->setPostbackData(
				array_merge($this->getPostbackData(), array($nameValuePair))
			);
		}
	}

	/**
	 * Remove PostbackData from the list.
	 * @param \PayPal\Api\NameValuePair $nameValuePair
	 * @return $this
	 * @deprecated Not publicly available
	 */
	public function removePostbackData($nameValuePair)
	{
		return $this->setPostbackData(
			array_diff($this->getPostbackData(), array($nameValuePair))
		);
	}

}
