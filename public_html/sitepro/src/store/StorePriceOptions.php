<?php

class StorePriceOptions {
	/** @var string */
	public $decimalPoint = '.';
	/** @var int */
	public $decimalPlaces = 2;
	/** @var string */
	public $thousandsSeparator = '';

	
	public function __construct() {}
	
	public function jsonSerialize() {
		return array(
			'decimalPoint' => $this->decimalPoint,
			'decimalPlaces' => $this->decimalPlaces,
			'thousandsSeparator' => $this->thousandsSeparator,
		);
	}
	
	/**
	 * Build instance from JSON string or standard object.
	 * @param string|stdClass $json JSON string to parse.
	 * @return StorePriceOptions
	 */
	public static function fromJson($json) {
		$data = is_object($json) ? $json : (is_string($json) ? json_decode($json) : (is_array($json) ? ((object) $json) : null));
		if (!is_object($data)) return null;
		$res = new self();
		foreach ($data AS $key => $value) { if (property_exists($res, $key)) $res->{$key} = $value; }
		return $res;
	}
	
}
