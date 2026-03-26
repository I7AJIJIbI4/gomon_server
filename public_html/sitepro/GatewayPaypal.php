<?php
require_once dirname(__FILE__).'/gateways/GatewayPaypalV2.php';
require_once dirname(__FILE__).'/gateways/GatewayPaypalV1.php';

class GatewayPaypal {
	/** @var stdClass */
	protected $config;

	/**
	 * @var PaymentGateway
	 */
	public $gateway;

	public function __construct(stdClass $config = null) {
		$this->config = ($config && is_object($config)) ? $config : new stdClass();
		$this->init();
	}

	public function init() {
		if (($input = $this->getFormParam('input'))) {
			$config = (object)\GatewayPaypalV2Auth::parseFromString($input);
			if ($config) {
				$this->config = (object)(array)$config;
			}
		}

		if (isset($this->config->clientId, $this->config->clientSecret) && $this->config->clientId && $this->config->clientSecret) {
			$this->gateway = new GatewayPaypalV2($this->config);
		} else {
			$this->gateway = new GatewayPaypalV1($this->config);
		}
	}

	public function doReturnAfterCallback() {
		return $this->gateway->doReturnAfterCallback();
	}

	public function requestCreatePayment() {
		if ($this->gateway instanceof GatewayPaypalV2) {
			return $this->gateway->requestCreatePayment();
		}
	}
	public function createInstantRedirectUrl($formVars) {
		return $this->gateway->createInstantRedirectUrl($formVars);
	}
	public function getTransactionId() {
		return $this->gateway->getTransactionId();
	}
	public function completeCheckout() {
		$this->gateway->completeCheckout();
	}

	public function createFormFields($formVars)
	{
		return $this->gateway->createFormFields($formVars);
	}


	/**
	 * Gets POST parameter
	 * @param string $name
	 * @param mixed $default
	 * @return string|null
	 */
	protected function getFormParam($name, $default = null) {
		if (isset($_POST[$name])) {
			return $_POST[$name];
		}
		return $default;
	}

	/**
	 * Gets GET parameter
	 * @param string $name
	 * @param mixed $default
	 * @return string|null
	 */
	protected function getQueryParam($name, $default = null) {
		if (!is_null(_get($name))) {
			return _get($name);
		}
		return $default;
	}

	public function __get($name)
	{
		return $this->gateway->$name;
	}

	public function __set($name, $value)
	{
		return $this->gateway->$name = $value;
	}

	public function __call($name, $arguments)
	{
		return call_user_func_array([$this->gateway, $name], $arguments);
	}

	public function __isset($name)
	{
		return isset($this->gateway->$name);
	}

	public function __unset($name)
	{
		unset($this->gateway->$name);
	}
}
