<?php

/**
 * Billing/Delivery info descriptor.
 */
class StoreBillingInfo extends stdClass {
	/** @var int Must be either 0 or 1 */
	public $isCompany = 0;
	/** @var string */
	public $companyName = '';
	/** @var string */
	public $companyCode = '';
	/** @var string */
	public $companyVatCode = '';
	/** @var string */
	public $email = '';
	/** @var string */
	public $firstName = '';
	/** @var string */
	public $lastName = '';
	/** @var string */
	public $address1 = '';
	/** @var string */
	public $address2 = '';
	/** @var string */
	public $city = '';
	/** @var string */
	public $region = '';
	/** @var string */
	public $regionCode = '';
	/** @var string */
	public $postCode = '';
	/** @var string */
	public $countryCode = '';
	/** @var string */
	public $country = '';
	/** @var string */
	public $phone = '';

	/**
	 * Build data to be used for JSON serialization.
	 * @return array
	 */
	public function jsonSerialize() {;
		return (array)$this;
	}

	/**
	 * Build instance from JSON string or standard object.
	 * @param string|stdClass $json JSON string to parse.
	 * @return StoreBillingInfo
	 */
	public static function fromJson($json) {
		$data = is_object($json) ? $json : (is_string($json) ? json_decode($json) : (is_array($json) ? ((object) $json) : null));
		if (!is_object($data)) return null;
		$res = new self();
		foreach ($data AS $key => $value) { $res->{$key} = $value; }
		return $res;
	}

}
