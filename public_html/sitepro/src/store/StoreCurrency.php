<?php

class StoreCurrency {
	/** @var string */
	public $code = 'USD';
	/** @var string */
	public $prefix = '$';
	/** @var string */
	public $postfix = '';
	
	public function __construct() {}
	
	public function jsonSerialize() {
		return array(
			'code' => $this->code,
			'prefix' => $this->prefix,
			'postfix' => $this->postfix,
		);
	}
	
	/**
	 * Build instance from JSON string or standard object.
	 * @param string|stdClass $json JSON string to parse.
	 * @return StoreCurrency
	 */
	public static function fromJson($json) {
		$data = is_object($json) ? $json : (is_string($json) ? json_decode($json) : (is_array($json) ? ((object) $json) : null));
		if (!is_object($data)) return null;
		$res = new self();
		foreach ($data AS $key => $value) { if (property_exists($res, $key)) $res->{$key} = $value; }
		return $res;
	}
	
}
