<?php

class StoreCoupon {
	const TYPE_PERCENTAGE = 0;
	const TYPE_FIXED_AMOUNT = 1;

	/** @var string */ public $code;
	/** @var int    */ public $type;
	/** @var float  */ public $value;
	
	/**
	 * @param string $code
	 * @param int $type
	 * @param float $value
	 */
	public function __construct($code = '', $type = self::TYPE_PERCENTAGE, $value = 0) {
		$this->code = $code;
		$this->type = $type;
		$this->value = $value;
	}

	/**
	 * @var object $data
	 * @return self
	 */
	public static function fromJson($data) {
		$result = new self();
		if (isset($data->code) && is_string($data->code)) {
			$result->code = $data->code;
		}
		if (isset($data->type) && is_int($data->type)) {
			$result->type = intval($data->type);
		}
		if (isset($data->value) && is_numeric($data->value)) {
			$result->value = floatval($data->value);
		}
		return $result;
	}
}
