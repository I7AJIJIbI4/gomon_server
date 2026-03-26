<?php

/**
 * Store cart descriptor.
 */
class StoreCartData {
	
	/** @var \Profis\SitePro\controller\StoreDataItem[] */
	public $items = array();
	/** @var StoreBillingInfo|null */
	public $billingInfo = null;
	/** @var StoreBillingInfo|null */
	public $deliveryInfo = null;
	/** @var int|string */
	public $shippingMethodId = 0;
	/** @var string */
	public $couponCode = '';
	/** @var string */
	public $orderComment = '';
	/** @var bool */
	public $userAgreedToTerms = false;
	
	/**
	 * @param string $id
	 * @param bool $fallbackToByItemId
	 * @return \Profis\SitePro\controller\StoreDataItem|null
	 */
	public function findItemById($id, $fallbackToByItemId = false) {
		foreach ($this->items as $item) {
			if ($item->cartId == $id) return $item;
		}
		if ($fallbackToByItemId) {
			foreach ($this->items as $item) {
				if ($item->id == $id) return $item;
			}
		}
		return null;
	}

	/**
	 * @param string $id
	 * @param bool $fallbackToByItemId
	 * @return \Profis\SitePro\controller\StoreDataItem|null
	 */
	public function removeItemById($id, $fallbackToByItemId = false) {
		foreach ($this->items as $idx => $item) {
			if ($item->cartId == $id) {
				array_splice($this->items, $idx, 1);
				return $item;
			}
		}
		if ($fallbackToByItemId) {
			foreach ($this->items as $idx => $item) {
				if ($item->id == $id) {
					array_splice($this->items, $idx, 1);
					return $item;
				}
			}
		}
		return null;
	}

	/** @return ?StoreCoupon */
	public function serializeCouponForJs() {
		if ($this->couponCode && ($c = StoreData::findCouponByCode($this->couponCode))) {
			return StoreCoupon::fromJson($c);
		} else {
			return null;
		}
	}

	/**
	 * @param string $imageResolution
	 * @return object[]
	 */
	public function serializeItemsForJs($imageResolution = '') {
		$currency = StoreData::getCurrency();
		$priceOptions = StoreData::getPriceOptions();
		$result = array();

		foreach ($this->items as $item) {
			$variant = StoreData::detectItemVariant($item, $item);
			$name = $variant ? StoreData::buildVariantName($variant, $item->name) : $item->name;
			$obj = (object) array(
				'id' => $item->id,
				'cartId' => ((isset($item->cartId) && $item->cartId) ? $item->cartId : $item->id),
				'name' => tr_($name),
				'sku' => $item->sku,
				'fullPriceStr' => StoreData::formatPrice($item->fullPrice, $priceOptions, $currency),
				'priceStr' => StoreData::formatPrice($item->price, $priceOptions, $currency),
				'price' => $item->price,
				'quantity' => StoreData::cartItemQuantity($item),
			);
			if ($imageResolution) {
				$obj->image = isset($item->image->image->{$imageResolution})
					? $item->image->image->{$imageResolution}
					: null;
			} else {
				$obj->image = StoreData::getAnyImageResolution($item->image->image);
			}
			$result[] = $obj;
		}

		return $result;
	}

	/**
	 * Build data to be used for JSON serialization.
	 * @return array
	 */
	public function jsonSerialize() {
		return array(
			'items' => $this->items,
			'billingInfo' => ($this->billingInfo ? $this->billingInfo->jsonSerialize() : null),
			'deliveryInfo' => ($this->deliveryInfo ? $this->deliveryInfo->jsonSerialize() : null),
			'shippingMethodId' => $this->shippingMethodId,
			'couponCode' => $this->couponCode,
			'orderComment' => $this->orderComment,
			'userAgreedToTerms' => $this->userAgreedToTerms,
		);
	}
	
	/**
	 * Build instance from JSON string or standard object.
	 * @param string|stdClass $json JSON string to parse.
	 * @return StoreCartData
	 */
	public static function fromJson($json) {
		$data = is_object($json) ? $json : (is_string($json) ? json_decode($json) : (is_array($json) ? ((object) $json) : null));
		if (!$data || !is_object($data)) return null;
		$res = new self();
		if (isset($data->items) && is_array($data->items)) $res->items = $data->items;
		if (isset($data->billingInfo)) $res->billingInfo = StoreBillingInfo::fromJson($data->billingInfo);
		if (isset($data->deliveryInfo)) $res->deliveryInfo = StoreBillingInfo::fromJson($data->deliveryInfo);
		if (isset($data->shippingMethodId)) $res->shippingMethodId = $data->shippingMethodId;
		if (isset($data->couponCode) && is_string($data->couponCode)) {
			$res->couponCode = $data->couponCode;
		}
		if (isset($data->orderComment)) $res->orderComment = (is_string($data->orderComment) ? $data->orderComment : '');
		if (isset($data->userAgreedToTerms)) $res->userAgreedToTerms = !!$data->userAgreedToTerms;
		return $res;
	}
	
}
