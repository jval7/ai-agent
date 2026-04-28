import type * as agentModel from "@domain/models/agent";
import * as dynamicListModule from "@adapters/inbound/react/components/form/DynamicList";
import * as paymentMethodItemModule from "@adapters/inbound/react/components/ProfessionalProfileForm/PaymentMethodItem";

function newPaymentMethod(): agentModel.PaymentMethod {
  return {
    currency: "COP",
    methodName: "",
    holder: null,
    instructions: null,
    appliesWhen: null
  };
}

interface PaymentMethodsSectionProps {
  value: agentModel.PaymentMethod[];
  onChange: (next: agentModel.PaymentMethod[]) => void;
  disabled: boolean;
}

export function PaymentMethodsSection(props: PaymentMethodsSectionProps) {
  return (
    <dynamicListModule.DynamicList
      addLabel="Agregar medio de pago"
      emptyMessage="No hay medios de pago configurados."
      items={props.value}
      newItemFactory={newPaymentMethod}
      onChange={props.onChange}
      renderItem={(item, _index, onItemChange) => (
        <paymentMethodItemModule.PaymentMethodItem
          disabled={props.disabled}
          onChange={onItemChange}
          value={item}
        />
      )}
    />
  );
}
