<?php

abstract class PaymentGateway {
	
	/** @var stdClass */
	protected $config;
	private $lastError = null;
	
	protected $returnAfterCallback = false;
	
	protected $sendMailAfterOrderSubmit = true;
	
	public function __construct(stdClass $config = null) {
		$this->config = ($config && is_object($config)) ? $config : new stdClass();
		$this->init();
	}
	
	/**
	 * Initiates class.
	 */
	public function init() {}
	
	/**
	 * Get order transaction ID during gateway callback
	 * @return string
	 */
	public abstract function getTransactionId();
	
	/**
	 * Get client info array during gateway callback
	 * @return array|null
	 */
	public function getClientInfo() {
		return null;
	}
	
	/**
	 * Gets last error if set.
	 * @return mixed
	 */
	public function getLastError() {
		return $this->lastError;
	}
	
	/**
	 * Sets last error if needed. 
	 * @param mixed $error
	 */
	public function setLastError($error) {
		$this->lastError = $error;
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
	
	/**
	 * Get request body as decoded JSON
	 * @param bool $associative
	 * @return mixed
	 */
	protected function getBodyAsJson($associative = false) {
		return json_decode(file_get_contents('php://input'), $associative);
	}
	
	/**
	 * If true then return action should be made
	 * right after callback action.
	 * @return boolean
	 */
	public function doReturnAfterCallback() {
		return $this->returnAfterCallback;
	}
	
	/**
	 * If true then will send mail for buyer and merchant
	 * after the order is submitted (not paid).
	 * @return boolean
	 */
	public function doSendMailAfterOrderSubmit() {
		return $this->sendMailAfterOrderSubmit;
	}

	/**
	 * Tells whether gateway actually supports callback URLs or not.
	 *
	 * If this method returns FALSE the payment api clears the cart and sends emails containing order information to seller and customer
	 * right after that order creation. Order doesn't get marked as complete.
	 *
	 * @param array $formVars
	 * @param StoreModuleOrder $order
	 * @return bool
	 */
	public function isCallbackSupported() { return true; }

	/**
	 * Returns new form HTML fields if needed
	 * to be inserted to gateway form before submit.
	 * @param array $formVars
	 * @return string[]
	 */
	public function createFormFields($formVars) {}

	/**
	 * Returns form HTML fields to delete if needed
	 * to be deleted from gateway form before submit.
	 * @return string[]
	 */
	public function deleteFormFields() {}
	
	/**
	 * Returns URL which must replace payment form action URL.
	 * @param array $formVars
	 * @return string
	 */
	public function createRedirectUrl($formVars) {}
	
	/**
	 * Returns URL which payment gateway should redirect by.
	 * @param array $formVars
	 * @return string
	 */
	public function createInstantRedirectUrl($formVars) {}
	
	/**
	 * Triggers payment callback script.
	 * @return boolean indicating if callback was successful.
	 * In case of "false" order is not marked as complete.
	 */
	public function callback(StoreModuleOrder $order = null) {
		return true;
	}
	
	/**
	 * Triggers payment verification script.
	 */
	public function verify(StoreModuleOrder $order = null) {}
	
	/**
	 * Triggers payment cancellation script.
	 */
	public function cancel() {}
	
	/**
	 * Triggers payment return script.
	 */
	public function completeCheckout() {}
	
}
