<?php

class StoreCartTotals {
	/** @var \Profis\SitePro\controller\StoreDataShippingMethod[] */
	public $shippingMethods = [];
	/** @var int|string */
	public $shippingMethodId = 0;
	/** @var float */
	public $subTotalPrice = 0;
	/** @var float */
	public $shippingPrice = 0;
	/** @var string */
	public $shippingMethod = '';
	/** @var StoreCartTotalsTax[] */
	public $taxes = [];
	/** @var float */
	public $discountPrice = 0;
	/** @var float */
	public $discountPercent = 0;
	/** @var float */
	public $totalWeight = 0;
	/** @var float */
	public $totalPrice = 0;
	/** @var ?StoreCoupon */
	public $coupon = null;
	/** @var string */
	public $couponError = '';
	/** @var object[] */
	public $items = [];

	/** @var ?object */
	public $billingInfo = null;
	/** @var ?object */
	public $deliveryInfo = null;
	/** @var bool */
	public $forceShowDeliveryInfo = false;
	/** @var string[]|null */
	public $billingInfoErrors = [];
	/** @var string[]|null */
	public $deliveryInfoErrors = [];
	/** @var string[]|null */
	public $generalErrors = [];
}

class StoreCartTotalsTax {
	/** @var float */
	public $rate = 0;
	/** @var float */
	public $ratePercent = 0;
	/** @var float */
	public $amount = 0;
	/** @var bool */
	public $shippingOnly = false;

	/** @param bool $shippingOnly */
	public function __construct($shippingOnly = false) {
		$this->shippingOnly = $shippingOnly;
	}

	/**
	 * @param float $dp
	 * @return void
	 */
	public function update($dp) {
		$this->ratePercent = round(($this->rate * 100) * 1000000) / 1000000;
		if ($this->amount > 0) $this->amount = round($this->amount * $dp) / $dp;
	}
}
