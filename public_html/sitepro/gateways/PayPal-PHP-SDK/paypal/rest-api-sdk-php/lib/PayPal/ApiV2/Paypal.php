<?php

namespace PayPal\ApiV2;

use PayPal\Common\PayPalModel;

/**
 * Class Paypal
 *
 * Paypal details.
 *
 * @package PayPal\ApiV2
 *
 * @property \PayPal\ApiV2\ExperienceContext experience_context
 */
class Paypal extends PayPalModel
{
	/**
	 * @param \PayPal\ApiV2\ExperienceContext $experience_context
	 *
	 * @return $this
	 */
	public function setExperienceContext($experience_context)
	{
		$this->experience_context = $experience_context;
		return $this;
	}

	/**
	 * @return \PayPal\ApiV2\ExperienceContext
	 */
	public function getExperienceContext()
	{
		return $this->experience_context;
	}
}
