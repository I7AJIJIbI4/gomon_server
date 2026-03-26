<?php

class StoreModuleOrderItemCustomField {
	/** @var string */
	public $name = "";
	/** @var string */
	public $value = "";

	public function __construct($name, $value) {
		$this->name = $name;
		$this->value = $value;
	}

	/**
	 * @param stdClass|array $data
	 * @return StoreModuleOrderItemCustomField
	 */
	public static function fromJson($data) {
		if( !is_object($data) )
			$data = (object)$data;
		$item = new self($data->name, $data->value);
		return $item;
	}

	public function jsonSerialize() {
		return array(
			"name" => $this->name,
			"value" => $this->value,
		);
	}

	public function __toString() {
		return "{$this->name}: {$this->value}";
	}
}