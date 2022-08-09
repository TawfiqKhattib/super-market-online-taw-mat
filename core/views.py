# from distutils.log import debug
# from doctest import DebugRunner
# import random
# from re import template
# from statistics import mode
from asyncio.windows_events import NULL
from distutils.command.config import config
import operator
from pyexpat import model
import random
from site import USER_SITE
import sqlite3
import string
from requests import request
# import django
# from django.db import models
import stripe
from django.conf import LazySettings, settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.views.generic import ListView, DetailView, View
# from django.views.generic.list import MultipleObjectTemplateResponseMixin, BaseListView, MultipleObjectMixin
from django.utils.functional import LazyObject, SimpleLazyObject
from django.contrib.auth.base_user import AbstractBaseUser

from .forms import CheckoutForm, CouponForm, RefundForm, PaymentForm
from .models import Item, OrderItem, Order, Address, Payment, Coupon, Refund, UserProfile
from django.views.generic.base import ContextMixin, TemplateResponseMixin, View
from debug_toolbar.panels.sql.forms import SQLSelectForm
from mlxtend.preprocessing import TransactionEncoder
from mlxtend.frequent_patterns import apriori, association_rules
import pandas as pd
import numpy as np

stripe.api_key = settings.STRIPE_SECRET_KEY

cart_items = []
requestUser = NULL
def get_CartItems():
    return cart_items

def create_ref_code():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))


def products(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, "product.html", context)


def is_valid_form(values):
    valid = True
    for field in values:
        if field == '':
            valid = False
    return valid


class CheckoutView(View):
    def get(self, *args, **kwargs):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            form = CheckoutForm()
            context = {
                'form': form,
                'couponform': CouponForm(),
                'order': order,
                'DISPLAY_COUPON_FORM': True
            }

            shipping_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='S',
                default=True
            )
            if shipping_address_qs.exists():
                context.update(
                    {'default_shipping_address': shipping_address_qs[0]})

            billing_address_qs = Address.objects.filter(
                user=self.request.user,
                address_type='B',
                default=True
            )
            if billing_address_qs.exists():
                context.update(
                    {'default_billing_address': billing_address_qs[0]})
            return render(self.request, "checkout.html", context)
        except ObjectDoesNotExist:
            messages.info(self.request, "You do not have an active order")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():

                use_default_shipping = form.cleaned_data.get(
                    'use_default_shipping')
                if use_default_shipping:
                    print("Using the defualt shipping address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='S',
                        default=True
                    )
                    if address_qs.exists():
                        shipping_address = address_qs[0]
                        order.shipping_address = shipping_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No default shipping address available")
                        return redirect('core:checkout')
                else:
                    print("User is entering a new shipping address")
                    shipping_address1 = form.cleaned_data.get(
                        'shipping_address')
                    shipping_address2 = form.cleaned_data.get(
                        'shipping_address2')
                    shipping_country = form.cleaned_data.get(
                        'shipping_country')
                    shipping_zip = form.cleaned_data.get('shipping_zip')

                    if is_valid_form([shipping_address1, shipping_country, shipping_zip]):
                        shipping_address = Address(
                            user=self.request.user,
                            street_address=shipping_address1,
                            apartment_address=shipping_address2,
                            country=shipping_country,
                            zip=shipping_zip,
                            address_type='S'
                        )
                        shipping_address.save()

                        order.shipping_address = shipping_address
                        order.save()

                        set_default_shipping = form.cleaned_data.get(
                            'set_default_shipping')
                        if set_default_shipping:
                            shipping_address.default = True
                            shipping_address.save()

                    else:
                        messages.info(
                            self.request, "Please fill in the required shipping address fields")

                use_default_billing = form.cleaned_data.get(
                    'use_default_billing')
                same_billing_address = form.cleaned_data.get(
                    'same_billing_address')

                if same_billing_address:
                    billing_address = shipping_address
                    billing_address.pk = None
                    billing_address.save()
                    billing_address.address_type = 'B'
                    billing_address.save()
                    order.billing_address = billing_address
                    order.save()

                elif use_default_billing:
                    print("Using the defualt billing address")
                    address_qs = Address.objects.filter(
                        user=self.request.user,
                        address_type='B',
                        default=True
                    )
                    if address_qs.exists():
                        billing_address = address_qs[0]
                        order.billing_address = billing_address
                        order.save()
                    else:
                        messages.info(
                            self.request, "No default billing address available")
                        return redirect('core:checkout')
                else:
                    print("User is entering a new billing address")
                    billing_address1 = form.cleaned_data.get(
                        'billing_address')
                    billing_address2 = form.cleaned_data.get(
                        'billing_address2')
                    billing_country = form.cleaned_data.get(
                        'billing_country')
                    billing_zip = form.cleaned_data.get('billing_zip')

                    if is_valid_form([billing_address1, billing_country, billing_zip]):
                        billing_address = Address(
                            user=self.request.user,
                            street_address=billing_address1,
                            apartment_address=billing_address2,
                            country=billing_country,
                            zip=billing_zip,
                            address_type='B'
                        )
                        billing_address.save()

                        order.billing_address = billing_address
                        order.save()

                        set_default_billing = form.cleaned_data.get(
                            'set_default_billing')
                        if set_default_billing:
                            billing_address.default = True
                            billing_address.save()

                    else:
                        messages.info(
                            self.request, "Please fill in the required billing address fields")

                payment_option = form.cleaned_data.get('payment_option')

                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                else:
                    messages.warning(
                        self.request, "Invalid payment option selected")
                    return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("core:order-summary")


class PaymentView(View):
    def get(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        if order.billing_address:
            context = {
                'order': order,
                'DISPLAY_COUPON_FORM': False,
                'STRIPE_PUBLIC_KEY' : settings.STRIPE_PUBLIC_KEY
            }
            # userprofile = self.request.user.userprofile
            # if userprofile.one_click_purchasing:
            #     # fetch the users card list
            #     cards = stripe.Customer.list_sources(
            #         userprofile.stripe_customer_id,
            #         limit=3,
            #         object='card'
            #     )
            #     card_list = cards['data']
            #     if len(card_list) > 0:
            #         # update the context with the default card
            #         context.update({
            #             'card': card_list[0]
            #         })
                    
            return render(self.request, "payment.html", context)
        else:
            messages.warning(
                self.request, "You have not added a billing address")
            return redirect("core:checkout")

    def post(self, *args, **kwargs):
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = PaymentForm(self.request.POST)
        
        # form2 = SQLSelectForm()
        # query = "insert into core_payment (amount, user_id) values (15,4)"
        # cursor = form2.cursor
        # cursor.execute(query)
        
        # userprofile = UserProfile.objects.get(user=self.request.user)
        
        if form.is_valid():
            token = form.cleaned_data.get('stripeToken')
            save = form.cleaned_data.get('save')
            use_default = form.cleaned_data.get('use_default')

            # if save:
                # if userprofile.stripe_customer_id != '' and userprofile.stripe_customer_id is not None:
                #     customer = stripe.Customer.retrieve(
                #         userprofile.stripe_customer_id)
                #     customer.sources.create(source=token)

                # else:
                #     customer = stripe.Customer.create(
                #         email=self.request.user.email,
                #     )
                #     customer.sources.create(source=token)
                #     userprofile.stripe_customer_id = customer['id']
                #     userprofile.one_click_purchasing = True
                #     userprofile.save()

            amount = int(order.get_total() * 100)

            try:

                if use_default or save:
                    # charge the customer because we cannot charge the token more than once
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="usd",
                        # customer=userprofile.stripe_customer_id
                    )
                else:
                    # charge once off on the token
                    charge = stripe.Charge.create(
                        amount=amount,  # cents
                        currency="usd",
                        source=token
                    )

                # create the payment
                payment = Payment()
                payment.stripe_charge_id = charge['id']
                payment.user = self.request.user
                payment.amount = order.get_total()
                orderItems = ','.join(str(v) for v in order.items.all())
                orderItems = orderItems.split(',')
                payment.items = ','.join(str(' '.join(item for item in orderitem.split(' ')[2:])) for orderitem in orderItems)
                print(payment.items)
                payment.save()
                
                # assign the payment to the order

                order_items = order.items.all()
                order_items.update(ordered=True)
                for item in order_items:
                    item.save()

                order.ordered = True
                order.payment = payment
                order.ref_code = create_ref_code()
                order.save()
                cart_items.clear()
                messages.success(self.request, "Your order was successful!")
                return redirect("/")

            except stripe.error.CardError as e:
                body = e.json_body
                err = body.get('error', {})
                messages.warning(self.request, f"{err.get('message')}")
                return redirect("/")

            except stripe.error.RateLimitError as e:
                # Too many requests made to the API too quickly
                messages.warning(self.request, "Rate limit error")
                return redirect("/")

            except stripe.error.InvalidRequestError as e:
                # Invalid parameters were supplied to Stripe's API
                print(e)
                messages.warning(self.request, "Invalid parameters")
                return redirect("/")

            except stripe.error.AuthenticationError as e:
                # Authentication with Stripe's API failed
                # (maybe you changed API keys recently)
                messages.warning(self.request, "Not authenticated")
                return redirect("/")

            except stripe.error.APIConnectionError as e:
                # Network communication with Stripe failed
                messages.warning(self.request, "Network error")
                return redirect("/")

            except stripe.error.StripeError as e:
                # Display a very generic error to the user, and maybe send
                # yourself an email
                messages.warning(
                    self.request, "Something went wrong. You were not charged. Please try again.")
                return redirect("/")

            except Exception as e:
                # send an email to ourselves
                messages.warning(
                    self.request, e)
                return redirect("/")

        messages.warning(self.request, "Invalid data received")
        return redirect("/payment/stripe/")





class OrderSummaryView(LoginRequiredMixin, View):
    def get(self, *args, **kwargs):
        try:
            # requestUser = self.request.user
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            lazyob = LazyObject()
            simpleLazyObject = SimpleLazyObject(lazyob)
            print(self.request.user)
            print("1111111111111111111111111111")
            print(order)
            print("22222222222222222222222222")
            print(context)
            print("333333333333333333333333333")
            print(self.request)
            print("444444444444444444444444444444")
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.warning(self.request, "You do not have an active order")
            return redirect("/")



    
class LegumeDetailView(ListView ):
    # ToDo : check if self.request.user not Anonymous render 
     
    #  te = TemplateResponseMixin
    #  mt = MultipleObjectTemplateResponseMixin #
    #  co = ContextMixin
    #  mo = MultipleObjectMixin
    #  view = View
    #  blv = BaseListView#
    #  lvl = ListView
     
     model=Item
    #  paginate_by = 4
     template_name = 'legumeCategory.html'
     
    
class VeggiesDetailView(ListView):
     model=Item
    #  paginate_by = 4
     template_name = 'veggiesCategory.html'
        
    
class MeatDetailView(ListView):
     model=Item
    #  paginate_by = 4
     template_name = 'meatCategory.html'
           
 
    
class MilkDetailView(ListView):
     model=Item
    #  paginate_by = 4
     template_name = 'milkCategory.html'
           


class OthersDetailView(ListView):
     model=Item
    #  paginate_by = 4
     template_name = 'othersCategory.html'
 
          
class RecommendedDetailView(ListView):
    # model=Item
    # template_name = 'recommendedCategory.html'
    def get(self, *args, **kwargs):
         try:
             # requestUser = self.request.user
            #  ListView.model=Item
            #  ListView.template_name = 'recommendedCategory.html'
             data=[]
             order = Order.objects.get(user=self.request.user, ordered=False)
            #  model = Item
             conn = sqlite3.connect("C:\\Users\\Win10\\Desktop\\django-ecommerce-master\\django-ecommerce\\FinalFile.sqli")
             cur = conn.cursor()
             payments = cur.execute("SELECT items from core_payment").fetchall()
             paymentsItems = ','.join(str(v) for v in payments)
             paymentsItems = paymentsItems.replace("('","").translate(({ord("["):""})).translate(({ord("]"):""})).split(",),")
            #  paymentsItems.pop()
            #  print(paymentsItems)
             for item in paymentsItems:
                newItem = item.split(',')
                # newItem.pop()
                # print("ssssssssssssssssssssssssssssssssssssssssssss")
                # print(newItem)
                if(newItem[0] == ""):
                    newItem.remove(newItem[0])
                
                newItem[len(newItem)-1] = ''.join(str(v) for v in list(newItem[len(newItem)-1].replace('"',"'"))[0:len(newItem[len(newItem)-1])-1])
                # print(newItem[len(newItem)-1])
                data.append(newItem)
                
             data[len(data)-1].pop()
             lastVar = data[len(data)-1]
            #  print(lastVar[len(lastVar)-1])
             lastVar[len(lastVar)-1] = ''.join(str(v) for v in list(lastVar[len(lastVar)-1].replace("'","")))
            #  print(lastVar[len(lastVar)-1])
            # ToDo here need to add ML to check supp and con
            #  print("kkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkkk")
            #  print(type(data[len(data)-1][1]))
            #  data[len(data)-1][1] = ''.join(str(v) for v in list(data[len(data)-1][1].replace('"',"'"))[0:len(data[len(data)-1][1])-1])
            #  print(''.join(str(v) for v in list(data[len(data)-1][1].replace('"',"'"))[0:len(data[len(data)-1][1])-2]))
             a = TransactionEncoder()
             a_data = a.fit(data).transform(data)
             df = pd.DataFrame(a_data,columns=a.columns_)
             df = df.replace(False,0)
            #  print(df)
             df = apriori(df, min_support = 0.1, use_colnames = True, verbose = 1)
             print(df)
             df_ar = association_rules(df, metric = "confidence", min_threshold = 0.1)
             print(df_ar)
             print(data)
             print("111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111111")
            
            #  allItemsData=[]
            #  allItemsData = items[11 : len(Item.objects.all())].replace("Item: ","").replace("<","").replace(">","").split(",")
            #  allItemsData = Item.objects.all()
            #  allItemsData = allItemsData[-len(Item.objects.all()) :]
            #  print(len(Item.objects.all()))
            #  print(allItemsData[0])
            #  print(allItemsData)
            #  print(Item.category.__get__(Item.objects.first()))
            #  print(allItemsData)
            #  listItems = TransactionEncoder()
            #  listItems_data = listItems.fit(allItemsData).transform(allItemsData)
            #  df_Items = pd.DataFrame(listItems_data,columns=listItems.columns_)
            #  df_Items = df_Items.replace(False,0)
            #  print(df_Items)
            #  df_Items = apriori(df_Items, min_support = 0.2, use_colnames = True, verbose = 1)
            #  print(df_Items)
            #  df_Items_ar = association_rules(df_Items, metric = "confidence", min_threshold = 0.6)
            #  print(df_Items_ar)
             
             confidenceObj={}
             print(Order.get_Items(order))
             for item in Order.get_Items(order):
                 for paymentItem in df_ar.iterrows():
                     val = list(paymentItem[1]["antecedents"])
                    #  print("22222222222222222222222222222222222222222222222222222222222222")
                    #  print(list(paymentItem[1]["antecedents"]))
                    #  print(item.getItem())
                     for antecval in val:
                        if(antecval == item.getItem()):
                            consequents = list(paymentItem[1]["consequents"])
                            confVal = paymentItem[1]["confidence"]
                            for consval in consequents:
                                # print("333333333333333333333333333333333333333333333333333333333333333333333333")
                                # print(consval)
                                # print(confVal)
                                confidenceObj[consval] = confVal
            
             
            #  for item in df_Items_ar.iterrows():
            #      itemval = list(item[1]["consequents"])[0]
            #      print(item)
            #      print("666666666666666666666666666666666")
            #      print(itemval)
            #      if  confidenceObj[itemval]:
            #          print("5555555555555555555555555555555555555555")
            #          print(item)       
            #          list(item[1]["consequents"])[0] = confidenceObj[itemval]
             
            #  allItems = df_Items_ar.sort_values('confidence', ascending=False)
            #  allItemsOrderd = []
            #  for item in allItems:
            #      allItemsOrderd.append(list(item[1]["antecedents"])[0])
            # ##########################################################################################
             arrayItems = []
             sorted(confidenceObj.values())
             print("44444444444444444444444444444444444444444444444444")
             print(confidenceObj)
            #  itemOrder={}
            #  conn = sqlite3.connect("C:\\Users\\Win10\\Desktop\\django-ecommerce-master\\django-ecommerce\\FinalFile.sqli")
            #  cur = conn.cursor()
             coreItems = cur.execute("SELECT * from core_recomended").fetchall()
            #  print(type(coreItems))
             if len(coreItems)==0:
                coreItems = cur.execute("SELECT * from core_item").fetchall()
            #  print(coreItems)
             cur.execute("DELETE from core_recomended").fetchall()
             
             listconfidenceObj=[]
             for k in confidenceObj.keys():
                listconfidenceObj.insert(0,k)
            #  print(listconfidenceObj)
             for k in listconfidenceObj:
                # print("99999999999999999999999999999999999")
                # print(k)
                # itemOrder = {
                #     "'title'" : k, "'category'" : "'"+Item.category.__get__(k)+"'", "'discount_price'" : "'"+Item.discount_price.__get__(k)+"'",
                #     "'discription'": "'"+Item.description.__get__(k)+"'", "'image'":"'"+Item.image.__get__(k)+"'", "'price'":"'"+Item.price.__get__(k)+"'",
                #     "'slug'":"'"+Item.slug.__get__(k)+"'", "'label":"'"+Item.label.__get__(k)+"'"    
                #   }
                #  itemOrder["title"] = k
                # arrayItems.append(newItem for newItem in coreItems if newItem["title"]==k) 
                for newItem in coreItems:
                    # print("999999999999999999999999999999999999999999988888888888888888888888888888888888565555555555555555555")
                    # print(newItem)
                    # print(k)
                    # print(newItem[1])
                    if newItem[1] == k:
                        print("99999999999999999999999999999999999")
                        print(newItem)
                        cur.execute("INSERT INTO core_recomended ( title, price, discount_price, category, label, slug, description, image ) VALUES(?, ?, ?, ?, ?, ?, ?, ? )", (newItem[1],newItem[2],newItem[3],newItem[4],newItem[5],newItem[6],newItem[7],newItem[8])).fetchall()
                        # print("999999999999999999999999999999999999999999988888888888888888888888888888888888565555555555555555555")
                        # print(cur.execute("SELECT * from core_recomended").fetchall())
                        arrayItems.append(newItem)
            #  {arrayItems.append
            #     ({
            #         "'title'" : k, "'category'" : Item.category.__get__(k), "'discount_price'" : Item.discount_price.__get__(k),
            #         "'discription'": Item.description.__get__(k), "'image'":Item.image.__get__(k), "'price'":Item.price.__get__(k),
            #         "'slug'":Item.slug.__get__(k), "'label":Item.label.__get__(k)    
            #     })
            #    for k,v in sorted(confidenceObj.items(), key=lambda item: item[1])}
             
            #  allItemsData.exclude(k for k in arrayItems)
             
            #  listAllItemsData = list(allItemsData)
            #  print(arrayItems)
            #  print(10101010101010101010101010110101010101010101011010101010101)
            #  print(listAllItemsData)
            #  listAllItemsData.remove(k for k in arrayItems if k in listAllItemsData)
            #  print("99999999999999999999999999999999999999999999999999999")
            #  print(arrayItems)
             for k in arrayItems:
                 if k in coreItems:
                     coreItems.remove(k)
                     
             for newItem in coreItems:
                #  if not arrayItems.__contains__(item):
                #      arrayItems.append({
                #     "'title'" : k, "'category'" : Item.category.__get__(k), "'discount_price'" : Item.discount_price.__get__(k),
                #     "'discription'": Item.description.__get__(k), "'image'":Item.image.__get__(k), "'price'":Item.price.__get__(k),
                #     "'slug'":Item.slug.__get__(k), "'label":Item.label.__get__(k)    
                # })
                #  print(newItem)
                 cur.execute("INSERT INTO core_recomended ( title, price, discount_price, category, label, slug, description, image ) VALUES(?, ?, ?, ?, ?, ?, ?, ? )",(newItem[1],newItem[2],newItem[3],newItem[4],newItem[5],newItem[6],newItem[7],newItem[8])).fetchall()
                 arrayItems.append(newItem)
             conn.commit()
            #  print("8888888888888888888888888888888888888888888888888888888888888888")
            #  print(arrayItems)
             
             context = {
                 'object': order,
                 'object_list': arrayItems,
                 'payment_list' : data
             }

             return render(self.request, 'recommendedCategory.html', context)
         except ObjectDoesNotExist:
             messages.warning(self.request, "You do not have an active order")
             return redirect("/")
    # model=Item
    # template_name = 'recommendedCategory.html'
    # model=Item
    # template_name = 'recommendedCategory.html'
    # cart_items = order 
    
    # context = {
    #              'object': cart_items
    #          }
    #  paginate_by = 4
    #  order = Order.objects.get(user=self.request.user, ordered=False)
    #  context = {
    #         'object': order
    #     }
    # template_name = 'recommendedCategory.html'


class ChatDetailView(ListView):
    # model=Item
    # template_name = 'recommendedCategory.html'
    def get(self, *args, **kwargs):
         try:
             
             conn = sqlite3.connect("C:\\Users\\Win10\\Desktop\\django-ecommerce-master\\django-ecommerce\\FinalFile.sqli")
             cur = conn.cursor()
            
             coreItems = cur.execute("SELECT username,email  from auth_user").fetchall()

             print(coreItems)
             context = {
                 'object_list': coreItems
                 
             }

             return render(self.request, 'Chat.html', context)
         except ObjectDoesNotExist:
             messages.warning(self.request, "You do not have an active order")
             return redirect("/")
         
         
class ItemDetailView(DetailView):
    model = Item
    template_name = "product.html"


class HomeView(ListView):
    model = Item
    # paginate_byl = 4
    # paginate_byv = 4
    # paginate_byme = 4
    # paginate_bymi = 4
    # paginate_byo = 4
    # le = LegumeDetailView
    # paginate_by = 4
    template_name = "home.html"
    
@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_item, created = OrderItem.objects.get_or_create(
        item=item,
        user=request.user,
        ordered=False
    )
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "This item quantity was updated.")
            return redirect("core:order-summary")
        else:
            cart_items.append(order_item)
            order.items.add(order_item)
            print("77777777777777777777777777777777777777777777777777777")
            print(cart_items)
            messages.info(request, "This item was added to your cart.")
            return redirect("core:order-summary")
    else:
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        cart_items.append(order_item)
        print("66666666666666666666666666666666666666666666666666666666666")
        print(cart_items)
        messages.info(request, "This item was added to your cart.")
        return redirect("core:order-summary")


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            order.items.remove(order_item)
            order_item.delete()
            messages.info(request, "This item was removed from your cart.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect("core:product", slug=slug)


@login_required
def remove_single_item_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user,
        ordered=False
    )
    if order_qs.exists():
        order = order_qs[0]
        # check if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item,
                user=request.user,
                ordered=False
            )[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
                order_item.save()
            else:
                order.items.remove(order_item)
            messages.info(request, "This item quantity was updated.")
            return redirect("core:order-summary")
        else:
            messages.info(request, "This item was not in your cart")
            return redirect("core:product", slug=slug)
    else:
        messages.info(request, "You do not have an active order")
        return redirect("core:product", slug=slug)


def get_coupon(request, code):
    try:
        coupon = Coupon.objects.get(code=code)
        return coupon
    except ObjectDoesNotExist:
        messages.info(request, "This coupon does not exist")
        return redirect("core:checkout")


class AddCouponView(View):
    def post(self, *args, **kwargs):
        form = CouponForm(self.request.POST or None)
        if form.is_valid():
            try:
                code = form.cleaned_data.get('code')
                order = Order.objects.get(
                    user=self.request.user, ordered=False)
                order.coupon = get_coupon(self.request, code)
                order.save()
                messages.success(self.request, "Successfully added coupon")
                return redirect("core:checkout")
            except ObjectDoesNotExist:
                messages.info(self.request, "You do not have an active order")
                return redirect("core:checkout")


class RequestRefundView(View):
    def get(self, *args, **kwargs):
        form = RefundForm()
        context = {
            'form': form
        }
        return render(self.request, "request_refund.html", context)

    def post(self, *args, **kwargs):
        form = RefundForm(self.request.POST)
        if form.is_valid():
            ref_code = form.cleaned_data.get('ref_code')
            message = form.cleaned_data.get('message')
            email = form.cleaned_data.get('email')
            # edit the order
            try:
                order = Order.objects.get(ref_code=ref_code)
                order.refund_requested = True
                order.save()

                # store the refund
                refund = Refund()
                refund.order = order
                refund.reason = message
                refund.email = email
                refund.save()

                messages.info(self.request, "Your request was received.")
                return redirect("core:request-refund")

            except ObjectDoesNotExist:
                messages.info(self.request, "This order does not exist.")
                return redirect("core:request-refund")
