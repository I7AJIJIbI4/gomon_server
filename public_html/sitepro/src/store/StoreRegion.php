<?php

class StoreRegion {
	
	/** @var string */
	public $code;
	/** @var string */
	public $name;
	
	/**
	 * @param $code string
	 * @param $name string
	 */
	public function __construct($code, $name) {
		$this->code = $code;
		$this->name = $name;
	}

	public static function create($code, $name) {
		return new static($code, $name);
	}
}
