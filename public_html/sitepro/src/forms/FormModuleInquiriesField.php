<?php

class FormModuleInquiriesField {
	/** @var bool */
	public $enabled = false;
	/** @var bool */
	public $required = false;
	/** @var string */
	public $type = "";
	/** @var array */
	public $settings = array();

	/** @var string|array */
	public $name = "";
	/** @var string|array */
	public $default = "";

	/** @var string|integer|array */
	public $answer = "";

	protected function __construct() {
	}

	/**
	 * @param stdClass|array $data
	 * @return self
	 */
	public static function fromJson($data) {
		if( !is_object($data) )
			$data = (object)$data;
		$item = new self();

		$item->enabled = isset($data->enabled) ? boolval($data->enabled) : true;
		$item->required = isset($data->required) ? boolval($data->required) : false;
		$item->type = isset($data->type) ? $data->type : 'input';
		$item->settings = isset($data->settings) ? $data->settings : array();
		$item->name = isset($data->name) ? $data->name : '';
		$item->default = isset($data->default) ? $data->default : '';
		$item->answer = isset($data->answer) ? $data->answer : '';
		return $item;
	}

	public function jsonSerialize() {
		return array(
			"enabled" => $this->enabled,
			"required" => $this->required,
			"type" => $this->type,
			"settings" => $this->settings,
			"name" => $this->name,
			"default" => $this->default,
			"answer" => $this->answer,
		);
	}
}